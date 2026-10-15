"""CAL 전체 사건 집합의 bounded temperature 학습과 v2 증거 재검산.

후보 및 NIL 모델은 고정한다. CAL 정답으로 양의 inverse temperature만
최적화하며 정책의 임계값과 FROZEN 자료는 최적화에 사용하지 않는다.
저장 증거의 결정적 replay는 수치 결과의 검산이지 새로운 학습 실행이나
원문/주석의 독립적인 진실 확인을 뜻하지 않는다. 파일 및 외부 I/O는 없다.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .candidate_set_calibration_shadow import (
    CalibrationArtifact, CalibrationEvaluationPolicy, CalibrationFitReceipt,
    CalibrationSplitAssignment, CalibrationSplitManifest,
)
from .candidate_reranker_calibration_data import (
    CalibrationFitEvent, calibration_event_set_sha256, validate_calibration_fit_events,
)


EVIDENCE_SCHEMA = "candidate_reranker_temperature_learning_evidence_v1"
REPORT_SCHEMA = "candidate_reranker_temperature_fit_report_v1"
RECEIPT_SCHEMA = "candidate_set_calibration_fit_receipt_v2"
ARTIFACT_SCHEMA = "candidate_set_calibration_artifact_v2"
DEFAULT_CONFIG = {"beta_min": 0.01, "beta_max": 100.0,
                  "max_iterations": 80, "beta_tolerance": 1e-10}
MAX_ROWS = 256
MAX_EVENTS_PER_ROW = 21
MAX_LOGIT_ABS = 10_000.0
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024


def _contract() -> dict:
    return {"schema_version": "candidate_reranker_temperature_solver_v1",
        "parameter": "INVERSE_TEMPERATURE_BETA", "temperature": "1/BETA",
        "objective": "UNWEIGHTED_MEAN_WHOLE_CAL_CANDIDATE_PLUS_NIL_NLL",
        "optimizer": "CONVEX_DERIVATIVE_BISECTION", "initial_beta": 1.0,
        "row_order": "EXTERNAL_MANIFEST_CAL_EXAMPLE_ID_ASCENDING",
        "labels": "BOUND_CANDIDATE_OPTION_ORDER_THEN_NIL",
        "flat_policy": "IDENTITY_BETA_1_NO_IDENTIFIABLE_TEMPERATURE",
        "boundary_policy": "ENDPOINT_DERIVATIVE_SIGN",
        "termination": "EXACT_ZERO_DERIVATIVE_OR_ABSOLUTE_BETA_BRACKET_WIDTH",
        "nonconvergence": "REJECT_NO_VALID_ARTIFACT",
        "max_rows": MAX_ROWS, "max_events_per_row": MAX_EVENTS_PER_ROW,
        "max_abs_logit": MAX_LOGIT_ABS, "max_iterations": 256,
        "max_evidence_bytes": MAX_EVIDENCE_BYTES,
        "beta_hard_bounds": [0.01, 100.0],
        "excluded": ["TRAIN_OPTIMIZATION", "DEV_LOGITS", "FROZEN_LOGITS", "THRESHOLD_FITTING"],
        "publication_authority": False,
        "evidence_scope": "DECLARED_BOUND_EVENTS_NOT_INDEPENDENT_ANNOTATION_VERIFICATION"}


SOLVER_CONTRACT = _contract()


class CalibrationLearningError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CalibrationLearningError(code)


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise CalibrationLearningError("JSON_INVALID") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        value = dict(value)
    raw = _bytes(value)
    _require(len(raw) <= MAX_EVIDENCE_BYTES, "EVIDENCE_BYTE_LIMIT")
    return json.loads(raw)


def _object(value: Any, keys: set, code: str) -> None:
    _require(type(value) is dict and set(value) == set(keys), code)


def _finite(value: Any, low: float, high: float, code: str) -> float:
    _require(type(value) in (int, float), code)
    try:
        result = float(value)
    except OverflowError as exc:
        raise CalibrationLearningError(code) from exc
    _require(math.isfinite(result) and low <= result <= high, code)
    return result


def _config(config: Any) -> dict:
    if config is None:
        config = {}
    _require(type(config) is dict and set(config) <= set(DEFAULT_CONFIG), "CONFIG_INVALID")
    result = {**DEFAULT_CONFIG, **config}
    result["beta_min"] = _finite(result["beta_min"], 0.01, 1.0, "BETA_BOUND_INVALID")
    result["beta_max"] = _finite(result["beta_max"], 1.0, 100.0, "BETA_BOUND_INVALID")
    _require(result["beta_min"] < result["beta_max"], "BETA_BOUND_INVALID")
    result["beta_tolerance"] = _finite(result["beta_tolerance"], 1e-14, 1e-3, "TOLERANCE_INVALID")
    _require(type(result["max_iterations"]) is int and 1 <= result["max_iterations"] <= 256,
             "ITERATION_LIMIT_INVALID")
    return result


def _numeric_rows(rows: Any) -> tuple:
    _require(type(rows) in (list, tuple) and 1 <= len(rows) <= MAX_ROWS, "CAL_ROW_LIMIT")
    result = []
    for scores, target in rows:
        _require(type(scores) in (list, tuple) and 2 <= len(scores) <= MAX_EVENTS_PER_ROW,
                 "EVENT_COUNT_INVALID")
        _require(type(target) is int and 0 <= target < len(scores), "TARGET_INDEX_INVALID")
        values = tuple(_finite(v, -MAX_LOGIT_ABS, MAX_LOGIT_ABS, "LOGIT_INVALID") for v in scores)
        maximum = max(values)
        centered = tuple(v - maximum for v in values)
        result.append((centered, target))
    return tuple(result)


def _objective(rows: tuple, beta: float) -> tuple[float, float, float]:
    losses, gradients, curvatures = [], [], []
    for scores, target in rows:
        weights = tuple(math.exp(beta * score) for score in scores)
        total = math.fsum(weights)
        probabilities = tuple(weight / total for weight in weights)
        mean = math.fsum(probability * score for probability, score in zip(probabilities, scores))
        losses.append(math.log(total) - beta * scores[target])
        gradients.append(math.fsum(probability * (score - scores[target])
                                   for probability, score in zip(probabilities, scores)))
        curvatures.append(math.fsum(probability * (score - mean) ** 2
                                    for probability, score in zip(probabilities, scores)))
    result = tuple(math.fsum(values) / len(rows) for values in (losses, gradients, curvatures))
    _require(all(math.isfinite(v) for v in result), "OBJECTIVE_NONFINITE")
    return result


def _solve(rows: Any, config: dict) -> dict:
    rows = _numeric_rows(rows)
    lower, upper = config["beta_min"], config["beta_max"]
    initial = _objective(rows, 1.0)
    low_value, high_value = _objective(rows, lower), _objective(rows, upper)
    endpoint_gradients = [low_value[1], high_value[1]]
    iterations = 0
    if all(all(value == scores[0] for value in scores) for scores, _ in rows):
        beta, status = 1.0, "FLAT_IDENTITY"
    elif low_value[1] >= 0.0:
        beta, status = lower, "LOWER_BOUND_OPTIMUM"
    elif high_value[1] <= 0.0:
        beta, status = upper, "UPPER_BOUND_OPTIMUM"
    else:
        status = "ITERATION_LIMIT"
        for iterations in range(1, config["max_iterations"] + 1):
            middle = lower + (upper - lower) / 2.0
            gradient = _objective(rows, middle)[1]
            if gradient == 0.0:
                lower = upper = middle
                status = "INTERIOR_EXACT_DERIVATIVE_ZERO"
                break
            if gradient < 0.0:
                lower = middle
            else:
                upper = middle
            if upper - lower <= config["beta_tolerance"]:
                status = "INTERIOR_BRACKET_CONVERGED"
                break
        _require(status != "ITERATION_LIMIT", "SOLVER_NOT_CONVERGED")
        # Include the identity in a final bracket containing it, so an exactly
        # optimal identity is never replaced by a numerically worse midpoint.
        beta = 1.0 if lower <= 1.0 <= upper else lower + (upper - lower) / 2.0
    final = _objective(rows, beta)
    _require(final[0] <= initial[0] + 1e-12 * max(1.0, initial[0]), "NLL_INCREASED")
    return {"status": status, "beta": beta, "temperature": 1.0 / beta,
        "nll_before": initial[0], "nll_after": final[0], "nll_improvement": initial[0] - final[0],
        "initial_beta": 1.0, "iterations": iterations, "bracket": [lower, upper],
        "bracket_gradient": [_objective(rows, lower)[1], _objective(rows, upper)[1]],
        "endpoint_gradient": endpoint_gradients, "gradient": final[1], "curvature": final[2],
        "converged": True, "identifiable": status != "FLAT_IDENTITY"}


def _manifest(value: Any) -> CalibrationSplitManifest:
    if isinstance(value, CalibrationSplitManifest):
        value = value.to_dict()
    value = _copy(value)
    try:
        _require(type(value) is dict and type(value.get("assignments")) is list,
                 "CAL_MANIFEST_INVALID")
        value["assignments"] = tuple(CalibrationSplitAssignment(**row) for row in value["assignments"])
        return CalibrationSplitManifest(**value)
    except (TypeError, ValueError, KeyError) as exc:
        raise CalibrationLearningError("CAL_MANIFEST_INVALID") from exc


def _policy(value: Any) -> CalibrationEvaluationPolicy:
    if isinstance(value, CalibrationEvaluationPolicy):
        value = value.to_dict()
    try:
        return CalibrationEvaluationPolicy(**_copy(value))
    except (TypeError, ValueError, KeyError) as exc:
        raise CalibrationLearningError("POLICY_INVALID") from exc


def _legacy_receipt(manifest, scorer, temperature) -> CalibrationFitReceipt:
    rows = [row for row in manifest.assignments if row.split == "CALIBRATION"]
    counts = Counter(row.truth_kind for row in rows)
    resolved = sum(row.truth_kind == "CANDIDATE" and row.binding_status == "UNIQUE"
                   and row.truth_label is not None for row in rows)
    return CalibrationFitReceipt.create(split_manifest_sha256=manifest.manifest_sha256,
        calibration_split_fingerprint=manifest.split_fingerprints["CALIBRATION"],
        scorer_fingerprint=scorer, fit_row_count=len(rows), candidate_truth_count=counts["CANDIDATE"],
        resolved_candidate_count=resolved, unresolved_candidate_count=counts["CANDIDATE"] - resolved,
        nil_truth_count=counts["NIL"], unjudged_count=counts["UNJUDGED"],
        method="TEMPERATURE_SCALING", temperature=temperature)


_SHARED_FIELDS = ("training_split_manifest_sha256", "calibration_manifest_sha256",
    "scorer_fingerprint", "scorer_summary_sha256", "model_sha256", "base_model_sha256", "data_kind")
_EVIDENCE_FIELDS = {"schema_version", "events", "event_set_sha256", "example_order_sha256",
    "split_manifest", "policy", "config", "config_sha256", "solver_contract", "solver_contract_sha256",
    "binding", "counts", "solver", "publication_authority", "actual_performance_evaluated", "evidence_sha256"}


def _bound_events(events, manifest, policy) -> tuple:
    assignments = sorted((a for a in manifest.assignments if a.split == "CALIBRATION"),
                         key=lambda a: a.example_id)
    events = validate_calibration_fit_events(events, expected_example_ids=[a.example_id for a in assignments])
    # Reconstruct after validation: all later evidence uses owned immutable events.
    events = tuple(CalibrationFitEvent.from_dict(e.to_dict()) for e in events)
    _require(events[0].calibration_manifest_sha256 == manifest.manifest_sha256,
             "EVENT_CAL_MANIFEST_MISMATCH")
    _require(events[0].data_kind != "SYNTHETIC_FIXTURE" or policy.policy_scope == "SYNTHETIC_CONTRACT_ONLY",
             "SYNTHETIC_ACTUAL_POLICY_CONFLICT")
    for event, assignment in zip(events, assignments):
        _require(event.post_id == assignment.post_id and event.truth_kind == assignment.truth_kind
                 and event.truth_label == assignment.truth_label
                 and event.candidate_set_fingerprint == assignment.candidate_set_fingerprint,
                 "EVENT_ASSIGNMENT_MISMATCH")
        _require(event.label_provenance["artifact_sha256"] == assignment.label_provenance_sha256,
                 "LABEL_PROVENANCE_MISMATCH")
        _require((assignment.truth_kind == "CANDIDATE" and assignment.binding_status == "UNIQUE"
                  and assignment.matched_candidate_ids == (event.truth_label,))
                 or (assignment.truth_kind == "NIL" and assignment.binding_status == "NOT_APPLICABLE"
                     and not assignment.matched_candidate_ids), "RESOLVED_CAL_ASSIGNMENT_REQUIRED")
    legacy = _legacy_receipt(manifest, events[0].scorer_fingerprint, 1.0)
    legacy.validate_against(manifest, policy)
    return events


def _evidence(events, manifest, policy, config) -> dict:
    rows = [(event.raw_scores, event.labels.index(event.truth_label)) for event in events]
    solver = _solve(rows, config)
    evidence = {"schema_version": EVIDENCE_SCHEMA, "events": [e.to_dict() for e in events],
        "event_set_sha256": calibration_event_set_sha256(events),
        "example_order_sha256": canonical_sha256([e.example_id for e in events]),
        "split_manifest": manifest.to_dict(), "policy": policy.to_dict(),
        "config": dict(config), "config_sha256": canonical_sha256(config),
        "solver_contract": _contract(), "solver_contract_sha256": canonical_sha256(_contract()),
        "binding": {key: getattr(events[0], key) for key in _SHARED_FIELDS},
        "counts": {"rows": len(events), "event_labels": sum(len(e.labels) for e in events),
            "truth": dict(sorted(Counter(e.truth_kind for e in events).items())),
            "label_grades": dict(sorted(Counter(e.label_provenance["grade"] for e in events).items()))},
        "solver": solver, "publication_authority": False, "actual_performance_evaluated": False}
    evidence["evidence_sha256"] = canonical_sha256(evidence)
    return _copy(evidence)


def fit_temperature(events, *, split_manifest: CalibrationSplitManifest,
                    policy: CalibrationEvaluationPolicy, config=None) -> dict:
    """외부 manifest의 CAL 전체 순서가 맞을 때만 v2 fit artifact를 반환한다.

    입력 events는 bridge가 결속한 CalibrationFitEvent 목록/튜플이다. 누락행,
    순서 변경, 혼합 모델, 불명 정답을 제외해 성공으로 만드는 경로는 없다.
    CAL raw score 생성은 이 함수의 책임이 아니며, 모델 파라미터는 변경하지 않는다.
    """
    _require(isinstance(split_manifest, CalibrationSplitManifest)
             and isinstance(policy, CalibrationEvaluationPolicy), "TYPED_CAL_CONTEXT_REQUIRED")
    manifest, checked_policy, config = _manifest(split_manifest), _policy(policy), _config(config)
    events = _bound_events(events, manifest, checked_policy)
    evidence = _evidence(events, manifest, checked_policy, config)
    temperature = evidence["solver"]["temperature"]
    old = _legacy_receipt(manifest, events[0].scorer_fingerprint, temperature)
    fields = old.payload_without_receipt_sha256()
    fields.update(schema_version=RECEIPT_SCHEMA, learning_evidence=evidence)
    receipt = CalibrationFitReceipt.create(**fields)
    artifact = CalibrationArtifact.create(schema_version=ARTIFACT_SCHEMA,
        split_manifest_sha256=manifest.manifest_sha256,
        calibration_split_fingerprint=manifest.split_fingerprints["CALIBRATION"],
        frozen_holdout_fingerprint=manifest.split_fingerprints["FROZEN_HOLDOUT"],
        scorer_fingerprint=events[0].scorer_fingerprint, policy_sha256=checked_policy.policy_sha256,
        fit_receipt=receipt, method="TEMPERATURE_SCALING", temperature=temperature)
    report = {"schema_version": REPORT_SCHEMA, "status": "FITTED", "data_kind": events[0].data_kind,
        "method": "TEMPERATURE_SCALING", "optimizer_executed": True,
        "model_parameters_updated": False, "thresholds_fitted": False,
        "binding": dict(evidence["binding"]), "counts": dict(evidence["counts"]),
        "solver": dict(evidence["solver"]), "config": dict(config),
        "learning_evidence_sha256": evidence["evidence_sha256"],
        "calibration_artifact_sha256": artifact.artifact_sha256,
        "fit_receipt_sha256": receipt.receipt_sha256, "policy_sha256": checked_policy.policy_sha256,
        "publication_authority": False, "actual_performance_evaluated": False,
        "limitations": ["CAL_FIT_NOT_FROZEN_QUALITY_EVALUATION", "LABEL_GRADE_NOT_UPGRADED",
            "DECLARED_EVENT_SOURCE_BINDING_NOT_INDEPENDENTLY_VERIFIED", "SHADOW_ONLY_NO_PUBLICATION"]}
    report["report_sha256"] = canonical_sha256(report)
    return {"artifact": artifact, "fit_report": report}


def validate_fit_evidence(evidence, receipt, *, split_manifest=None, policy=None, artifact=None) -> None:
    """저장된 v2 증거·외부 좌표·결정적 수치 결과를 재검산한다. I/O/재학습은 없다.

    v2 receipt/Artifact validator를 다시 호출하지 않는다. typed v1 receipt로
    기존 CAL/DEV gate만 재사용하므로 legacy 소비 경로에서 호출해도 재귀하지 않는다.
    """
    _require(isinstance(receipt, CalibrationFitReceipt) and receipt.schema_version == RECEIPT_SCHEMA,
             "V2_FIT_RECEIPT_REQUIRED")
    evidence = _copy(evidence)
    _object(evidence, _EVIDENCE_FIELDS, "FIT_EVIDENCE_FIELDS_INVALID")
    _require(evidence["schema_version"] == EVIDENCE_SCHEMA, "FIT_EVIDENCE_SCHEMA_INVALID")
    _require(evidence["evidence_sha256"] == canonical_sha256({k: v for k, v in evidence.items()
             if k != "evidence_sha256"}), "FIT_EVIDENCE_SHA_MISMATCH")
    _require(_bytes(evidence) == _bytes(_copy(receipt.learning_evidence)), "RECEIPT_EVIDENCE_MISMATCH")
    _require(receipt.receipt_sha256 == canonical_sha256(receipt.payload_without_receipt_sha256()),
             "FIT_RECEIPT_SHA_MISMATCH")
    manifest, checked_policy = _manifest(evidence["split_manifest"]), _policy(evidence["policy"])
    if split_manifest is not None:
        _require(_bytes(_manifest(split_manifest).to_dict()) == _bytes(manifest.to_dict()),
                 "EXTERNAL_CAL_MANIFEST_MISMATCH")
    if policy is not None:
        _require(_bytes(_policy(policy).to_dict()) == _bytes(checked_policy.to_dict()),
                 "EXTERNAL_POLICY_MISMATCH")
    config = _config(evidence["config"])
    _object(evidence["config"], set(DEFAULT_CONFIG), "STORED_CONFIG_INCOMPLETE")
    _require(type(evidence["events"]) is list and 1 <= len(evidence["events"]) <= MAX_ROWS,
             "CAL_ROW_LIMIT")
    events = _bound_events([CalibrationFitEvent.from_dict(item) for item in evidence["events"]],
                          manifest, checked_policy)
    expected = _evidence(events, manifest, checked_policy, config)
    _require(_bytes(evidence) == _bytes(expected), "FIT_EVIDENCE_REPLAY_MISMATCH")
    old = _legacy_receipt(manifest, events[0].scorer_fingerprint, expected["solver"]["temperature"])
    actual = receipt.payload_without_receipt_sha256()
    actual.pop("learning_evidence")
    actual["schema_version"] = old.schema_version
    _require(_bytes(actual) == _bytes(old.payload_without_receipt_sha256()), "FIT_RECEIPT_RESULT_MISMATCH")
    if artifact is not None:
        _require(isinstance(artifact, CalibrationArtifact) and artifact.schema_version == ARTIFACT_SCHEMA,
                 "V2_ARTIFACT_REQUIRED")
        expected_outer = {"split_manifest_sha256": manifest.manifest_sha256,
            "calibration_split_fingerprint": manifest.split_fingerprints["CALIBRATION"],
            "frozen_holdout_fingerprint": manifest.split_fingerprints["FROZEN_HOLDOUT"],
            "scorer_fingerprint": old.scorer_fingerprint, "policy_sha256": checked_policy.policy_sha256,
            "method": "TEMPERATURE_SCALING", "temperature": old.temperature,
            "fit_split": "CALIBRATION", "evaluation_split": "FROZEN_HOLDOUT", "status": "VALID"}
        _require(all(getattr(artifact, key) == value for key, value in expected_outer.items())
                 and _bytes(artifact.fit_receipt.to_dict()) == _bytes(receipt.to_dict()),
                 "ARTIFACT_EVIDENCE_BINDING_MISMATCH")
        _require(artifact.artifact_sha256 == canonical_sha256(artifact.payload_without_artifact_sha256()),
                 "ARTIFACT_SHA_MISMATCH")
