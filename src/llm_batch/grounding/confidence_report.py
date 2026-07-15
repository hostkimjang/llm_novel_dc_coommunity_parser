"""OFF-by-default typed confidence reports and policy-independent metrics.

This module deliberately does not import the production writer or route a
publication decision.  It keeps four concepts separate: candidate generation
completion, candidate/NIL label space, a calibrated *per-row* probability,
and aggregate quality metrics.  In particular, a percentage in a report is
not an accuracy claim; aggregate metrics are estimable only from
``FROZEN_ACTUAL`` labelled rows.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

from .calibration_actual_readback import (
    ArtifactRef,
    snapshot_json_object,
    snapshot_jsonl_rows,
)
from .candidate_set_shadow import (
    CandidateSet,
    LabelProbability,
    NIL_LABEL,
    candidate_set_from_dict,
)


SCHEMA_VERSION = "typed_confidence_report_v1"
METRICS_SCHEMA_VERSION = "typed_confidence_metrics_readback_v1"
EVIDENCE_MODES = frozenset({"NO_EXTERNAL_EVIDENCE", "SYNTHETIC_CONTRACT_ONLY", "FROZEN_ACTUAL"})
PROBABILITY_STATUSES = frozenset({"UNCALIBRATED", "CALIBRATED_SHADOW", "CALIBRATED_FROZEN_ACTUAL"})
SHADOW_ACTIONS = frozenset({"ABSTAIN", "SHADOW_SELECT"})
REQUIRED_FROZEN_ARTIFACT_NAMES = (
    "candidate_set",
    "source",
    "label",
    "calibration",
    "prediction",
)


def _strict_text(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field} must be non-empty")
    return result


def _strict_probability(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{field} must be finite within [0, 1]")
    return result


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _strict_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be a lowercase sha256")
    return value


def _deterministic_argmax(event_probabilities: Sequence[LabelProbability]) -> str:
    """Return the lexicographically smallest label among equal maxima."""

    available = [(float(item.probability), item.label) for item in event_probabilities if item.probability is not None]
    if not available:
        raise ValueError("argmax requires available probabilities")
    maximum = max(item[0] for item in available)
    return min(label for probability, label in available if probability == maximum)


def _validate_artifact_ref(ref: ArtifactRef) -> None:
    _strict_text(ref.logical_name, "artifact logical_name")
    relative = Path(_strict_text(ref.relative_path, "artifact relative_path"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact relative_path must stay below artifact_root")
    if isinstance(ref.bytes, bool) or not isinstance(ref.bytes, int) or ref.bytes < 0:
        raise ValueError("artifact bytes must be a non-negative integer")
    _strict_sha256(ref.sha256, "artifact sha256")
    _strict_sha256(ref.canonical_payload_sha256, "artifact canonical_payload_sha256")
    if ref.row_count is not None and (
        isinstance(ref.row_count, bool) or not isinstance(ref.row_count, int) or ref.row_count < 0
    ):
        raise ValueError("artifact row_count must be null or a non-negative integer")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


@dataclass(frozen=True)
class TypedConfidenceReport:
    """One observational confidence record; it is never a public decision."""

    post_id: str
    candidate_set_fingerprint: str
    producer_generation_status: str
    candidate_set_recall_status: str
    event_probabilities: Tuple[LabelProbability, ...]
    probability_status: str
    selected_label: Optional[str]
    selected_probability: Optional[float]
    confidence_percentage: Optional[float]
    shadow_action: str
    action_applied: bool
    operational_effect: str
    evidence_mode: str
    evidence_artifacts: Tuple[ArtifactRef, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "post_id", _strict_text(self.post_id, "post_id"))
        fingerprint = str(self.candidate_set_fingerprint or "").lower()
        if len(fingerprint) != 64 or any(ch not in "0123456789abcdef" for ch in fingerprint):
            raise ValueError("candidate_set_fingerprint must be a sha256")
        object.__setattr__(self, "candidate_set_fingerprint", fingerprint)
        if self.producer_generation_status not in {"COMPLETE", "TRUNCATED", "UNKNOWN"}:
            raise ValueError("unsupported producer_generation_status")
        expected_recall = (
            "READY_FOR_GOLD_EVALUATION"
            if self.producer_generation_status == "COMPLETE"
            else f"NOT_EVALUABLE_GENERATION_{self.producer_generation_status}"
        )
        if self.candidate_set_recall_status != expected_recall:
            raise ValueError("candidate_set_recall_status must be derived from producer completion")
        object.__setattr__(self, "event_probabilities", tuple(self.event_probabilities))
        labels = [item.label for item in self.event_probabilities]
        if not labels or labels[-1] != NIL_LABEL or len(labels) != len(set(labels)):
            raise ValueError("event probabilities must have unique labels ending in NIL")
        values = [item.probability for item in self.event_probabilities]
        available = [item is not None for item in values]
        if any(available) and not all(available):
            raise ValueError("probabilities must be all-null or all-present")
        if self.probability_status not in PROBABILITY_STATUSES:
            raise ValueError("unsupported probability_status")
        if self.evidence_mode not in EVIDENCE_MODES:
            raise ValueError("unsupported evidence_mode")
        artifacts = tuple(self.evidence_artifacts)
        for ref in artifacts:
            if not isinstance(ref, ArtifactRef):
                raise ValueError("evidence_artifacts must contain ArtifactRef values")
            _validate_artifact_ref(ref)
        artifact_names = tuple(ref.logical_name for ref in artifacts)
        artifact_paths = tuple(ref.relative_path for ref in artifacts)
        if self.evidence_mode == "FROZEN_ACTUAL":
            if len(artifact_names) != len(set(artifact_names)) or set(artifact_names) != set(REQUIRED_FROZEN_ARTIFACT_NAMES):
                raise ValueError("FROZEN_ACTUAL requires exact candidate_set/source/label/calibration/prediction refs")
            if len(artifact_paths) != len(set(artifact_paths)):
                raise ValueError("FROZEN_ACTUAL artifact paths must be distinct")
            by_name = {ref.logical_name: ref for ref in artifacts}
            artifacts = tuple(by_name[name] for name in REQUIRED_FROZEN_ARTIFACT_NAMES)
        elif artifacts:
            raise ValueError("non-actual reports cannot carry FROZEN_ACTUAL artifact refs")
        object.__setattr__(self, "evidence_artifacts", artifacts)
        if self.shadow_action not in SHADOW_ACTIONS:
            raise ValueError("unsupported shadow_action")
        if self.action_applied or self.operational_effect != "NONE_SHADOW_ONLY":
            raise ValueError("typed confidence reports must not affect public output")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported schema_version")
        if self.producer_generation_status != "COMPLETE":
            if any(available):
                raise ValueError("incomplete producer must keep all probabilities null")
            if self.probability_status != "UNCALIBRATED":
                raise ValueError("incomplete producer must be UNCALIBRATED")
            if any(value is not None for value in (self.selected_label, self.selected_probability, self.confidence_percentage)):
                raise ValueError("incomplete producer cannot select a label or percentage")
            if self.shadow_action != "ABSTAIN":
                raise ValueError("incomplete producer must ABSTAIN")
        if all(available):
            if abs(sum(float(item) for item in values if item is not None) - 1.0) > 1e-9:
                raise ValueError("probabilities must sum to 1")
            if self.probability_status == "UNCALIBRATED":
                raise ValueError("available probabilities require a calibrated status")
            if self.probability_status == "CALIBRATED_FROZEN_ACTUAL" and self.evidence_mode != "FROZEN_ACTUAL":
                raise ValueError("frozen calibrated probability requires FROZEN_ACTUAL evidence")
            if self.probability_status == "CALIBRATED_SHADOW" and self.evidence_mode == "FROZEN_ACTUAL":
                raise ValueError("FROZEN_ACTUAL evidence requires its explicit calibrated status")
            if self.selected_label not in labels or self.selected_probability is None or self.confidence_percentage is None:
                raise ValueError("calibrated reports require selected label, probability, and percentage")
            selected = _strict_probability(self.selected_probability, "selected_probability")
            lookup = {item.label: item.probability for item in self.event_probabilities}
            if abs(selected - float(lookup[self.selected_label])) > 1e-12:
                raise ValueError("selected_probability must equal the selected label probability")
            if isinstance(self.confidence_percentage, bool) or not isinstance(self.confidence_percentage, (int, float)):
                raise ValueError("confidence_percentage must be a number")
            percentage = _strict_probability(self.confidence_percentage / 100.0, "confidence_percentage") * 100.0
            if abs(percentage - selected * 100.0) > 1e-9:
                raise ValueError("confidence_percentage is a per-row probability percentage, not an accuracy")
            if self.selected_label != _deterministic_argmax(self.event_probabilities):
                raise ValueError("selected_label must be the deterministic argmax")
        else:
            if self.probability_status != "UNCALIBRATED":
                raise ValueError("all-null probabilities must be uncalibrated")
            if any(value is not None for value in (self.selected_label, self.selected_probability, self.confidence_percentage)):
                raise ValueError("uncalibrated report cannot contain a confidence percentage or selected label")
            if self.shadow_action != "ABSTAIN":
                raise ValueError("uncalibrated report must abstain")

    @classmethod
    def from_candidate_set(
        cls,
        candidate_set: CandidateSet,
        *,
        post_id: str,
        event_probabilities: Sequence[LabelProbability],
        probability_status: str,
        selected_label: Optional[str],
        selected_probability: Optional[float],
        confidence_percentage: Optional[float],
        shadow_action: str,
        evidence_mode: str,
        evidence_artifacts: Sequence[ArtifactRef] = (),
    ) -> "TypedConfidenceReport":
        expected_labels = tuple(
            candidate.candidate_id
            for candidate in candidate_set.candidates
            if candidate.event_eligible
        ) + (NIL_LABEL,)
        actual_labels = tuple(item.label for item in event_probabilities)
        if actual_labels != expected_labels:
            raise ValueError("event probabilities must exactly match event-eligible CandidateSet ids followed by NIL")
        return cls(
            post_id=post_id,
            candidate_set_fingerprint=candidate_set.candidate_set_fingerprint,
            producer_generation_status=candidate_set.generation_status,
            candidate_set_recall_status=candidate_set.candidate_set_recall_status,
            event_probabilities=tuple(event_probabilities),
            probability_status=probability_status,
            selected_label=selected_label,
            selected_probability=selected_probability,
            confidence_percentage=confidence_percentage,
            shadow_action=shadow_action,
            action_applied=False,
            operational_effect="NONE_SHADOW_ONLY",
            evidence_mode=evidence_mode,
            evidence_artifacts=tuple(evidence_artifacts),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "post_id": self.post_id,
            "candidate_set_fingerprint": self.candidate_set_fingerprint,
            "producer_generation_status": self.producer_generation_status,
            "candidate_set_recall_status": self.candidate_set_recall_status,
            "nil_label": NIL_LABEL,
            "event_probabilities": [item.to_dict() for item in self.event_probabilities],
            "probability_status": self.probability_status,
            "selected_label": self.selected_label,
            "selected_probability": self.selected_probability,
            "confidence_percentage": self.confidence_percentage,
            "percentage_semantics": "PER_ROW_CALIBRATED_PROBABILITY_NOT_ACCURACY",
            "shadow_action": self.shadow_action,
            "action_applied": self.action_applied,
            "operational_effect": self.operational_effect,
            "evidence_mode": self.evidence_mode,
            "evidence_artifacts": [ref.to_dict() for ref in self.evidence_artifacts],
        }


@dataclass(frozen=True)
class ConfidenceEvaluationRow:
    report: TypedConfidenceReport
    gold_label: str

    def __post_init__(self) -> None:
        gold = _strict_text(self.gold_label, "gold_label")
        object.__setattr__(self, "gold_label", gold)


def _validate_frozen_artifacts(rows: Sequence[ConfidenceEvaluationRow], artifact_root: str | Path) -> None:
    """Re-read every bound artifact and bind the report to its CandidateSet."""

    for row in rows:
        refs = {ref.logical_name: ref for ref in row.report.evidence_artifacts}
        candidate_ref = refs["candidate_set"]
        if Path(candidate_ref.relative_path).suffix.lower() != ".json":
            raise ValueError("candidate_set artifact must be a JSON object")
        current_candidate_ref, candidate_payload = snapshot_json_object(
            artifact_root,
            "candidate_set",
            candidate_ref.relative_path,
        )
        if current_candidate_ref.to_dict() != candidate_ref.to_dict():
            raise ValueError("artifact snapshot mismatch: candidate_set")
        try:
            bound_candidate_set = candidate_set_from_dict(candidate_payload)
        except ValueError as exc:
            raise ValueError(f"candidate_set artifact contract invalid: {exc}") from exc
        if bound_candidate_set.candidate_set_fingerprint != row.report.candidate_set_fingerprint:
            raise ValueError("candidate_set artifact fingerprint mismatch")
        expected_labels = [
            candidate.candidate_id
            for candidate in bound_candidate_set.candidates
            if candidate.event_eligible
        ] + [NIL_LABEL]
        report_labels = [item.label for item in row.report.event_probabilities]
        if report_labels != expected_labels:
            raise ValueError("report labels do not match the bound CandidateSet")

        def bound_rows(logical_name: str) -> list[dict[str, Any]]:
            stored = refs[logical_name]
            suffix = Path(stored.relative_path).suffix.lower()
            if suffix == ".json":
                current, payload = snapshot_json_object(
                    artifact_root, logical_name, stored.relative_path
                )
                values = [payload]
            elif suffix == ".jsonl":
                current, values = snapshot_jsonl_rows(
                    artifact_root, logical_name, stored.relative_path
                )
            else:
                raise ValueError(f"{logical_name} artifact must be JSON or JSONL")
            if current.to_dict() != stored.to_dict():
                raise ValueError(f"artifact snapshot mismatch: {logical_name}")
            return values

        source_matches = [
            value
            for value in bound_rows("source")
            if value.get("post_id") == row.report.post_id
        ]
        if len(source_matches) != 1:
            raise ValueError("source artifact must contain exactly one matching post_id")

        label_matches = [
            value
            for value in bound_rows("label")
            if value.get("post_id") == row.report.post_id
        ]
        if len(label_matches) != 1:
            raise ValueError("label artifact must contain exactly one matching post_id")
        expected_label = {
            "post_id": row.report.post_id,
            "gold_label": row.gold_label,
            "candidate_set_fingerprint": row.report.candidate_set_fingerprint,
            "source_artifact_sha256": refs["source"].sha256,
        }
        if label_matches[0] != expected_label:
            raise ValueError("label artifact semantic binding mismatch")

        calibration_values = bound_rows("calibration")
        if len(calibration_values) != 1:
            raise ValueError("calibration artifact must contain one object")
        calibration = calibration_values[0]
        calibration_fingerprint = _strict_sha256(
            calibration.get("calibration_fingerprint"),
            "calibration_fingerprint",
        )
        if calibration.get("candidate_set_artifact_sha256") != refs["candidate_set"].sha256:
            raise ValueError("calibration artifact CandidateSet binding mismatch")

        prediction_matches = [
            value
            for value in bound_rows("prediction")
            if value.get("post_id") == row.report.post_id
        ]
        if len(prediction_matches) != 1:
            raise ValueError("prediction artifact must contain exactly one matching post_id")
        expected_prediction = {
            "post_id": row.report.post_id,
            "candidate_set_fingerprint": row.report.candidate_set_fingerprint,
            "source_artifact_sha256": refs["source"].sha256,
            "label_artifact_sha256": refs["label"].sha256,
            "calibration_artifact_sha256": refs["calibration"].sha256,
            "calibration_fingerprint": calibration_fingerprint,
            "event_probabilities": [item.to_dict() for item in row.report.event_probabilities],
            "selected_label": row.report.selected_label,
            "selected_probability": row.report.selected_probability,
            "confidence_percentage": row.report.confidence_percentage,
        }
        if prediction_matches[0] != expected_prediction:
            raise ValueError("prediction artifact semantic binding mismatch")


def read_policy_independent_metrics(
    rows: Sequence[ConfidenceEvaluationRow],
    *,
    ece_bins: int = 10,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Compute descriptive metrics only; this function contains no pass policy.

    Synthetic rows and uncalibrated rows return an explicit non-estimable
    payload rather than a convenient percentage.  Threshold comparison, CI
    policy, and any routing decision intentionally belong to other layers.
    """

    if isinstance(ece_bins, bool) or not isinstance(ece_bins, int) or ece_bins < 2:
        raise ValueError("ece_bins must be an integer >= 2")
    rows = tuple(rows)
    base = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "reader_policy": "NONE_DESCRIPTIVE_ONLY",
        "input_rows": len(rows),
        "ece_bins": ece_bins,
        "aurc_tie_policy": "GROUP_END_RISK_REPEATED",
        "metric_denominators": {
            "scored_rows": 0,
            "candidate_set_recall_non_nil_gold_rows": 0,
            "selective_covered_rows": 0,
        },
        "metrics": {
            key: None
            for key in ("top_label_accuracy", "candidate_set_recall", "brier", "log_loss", "ece", "selective_risk", "aurc", "coverage")
        },
    }
    if not rows:
        return {**base, "status": "NOT_ESTIMABLE_EMPTY"}
    if any(row.report.evidence_mode != "FROZEN_ACTUAL" for row in rows):
        return {**base, "status": "NOT_ESTIMABLE_NOT_FROZEN_ACTUAL"}
    if any(row.report.probability_status != "CALIBRATED_FROZEN_ACTUAL" for row in rows):
        return {**base, "status": "NOT_ESTIMABLE_UNCALIBRATED"}
    if artifact_root is None:
        return {**base, "status": "NOT_ESTIMABLE_ARTIFACT_ROOT_REQUIRED"}
    _validate_frozen_artifacts(rows, artifact_root)

    correct: list[float] = []
    brier: list[float] = []
    log_loss: list[float] = []
    confidence_outcomes: list[tuple[float, float]] = []
    automatic: list[float] = []
    candidate_recall_eligible: list[float] = []
    candidate_recall_hits: list[float] = []
    for row in rows:
        probabilities = {item.label: float(item.probability) for item in row.report.event_probabilities}
        selected = row.report.selected_label
        selected_probability = float(row.report.selected_probability or 0.0)
        hit = float(selected == row.gold_label)
        correct.append(hit)
        brier_value = sum((value - float(label == row.gold_label)) ** 2 for label, value in probabilities.items())
        if row.gold_label not in probabilities:
            brier_value += 1.0
        brier.append(brier_value)
        log_loss.append(-math.log(max(probabilities.get(row.gold_label, 0.0), 1e-15)))
        confidence_outcomes.append((selected_probability, hit))
        if row.report.shadow_action == "SHADOW_SELECT":
            automatic.append(hit)
        if row.gold_label != NIL_LABEL:
            candidate_recall_eligible.append(1.0)
            candidate_recall_hits.append(float(row.gold_label in probabilities))

    bins: list[list[tuple[float, float]]] = [[] for _ in range(ece_bins)]
    for confidence, hit in confidence_outcomes:
        bins[min(int(confidence * ece_bins), ece_bins - 1)].append((confidence, hit))
    ece = sum((len(group) / len(rows)) * abs(_mean([item[0] for item in group]) - _mean([item[1] for item in group])) for group in bins if group)
    grouped: dict[float, list[float]] = {}
    for confidence, hit in confidence_outcomes:
        grouped.setdefault(confidence, []).append(hit)
    errors = 0.0
    covered = 0
    risks: list[float] = []
    for confidence in sorted(grouped, reverse=True):
        group = grouped[confidence]
        errors += sum(1.0 - hit for hit in group)
        covered += len(group)
        risks.extend([errors / covered] * len(group))
    metrics = base["metrics"]
    metrics.update(
        {
            "top_label_accuracy": _mean(correct),
            "candidate_set_recall": _mean(candidate_recall_hits),
            "brier": _mean(brier),
            "log_loss": _mean(log_loss),
            "ece": ece,
            "selective_risk": (1.0 - _mean(automatic)) if automatic else None,
            "aurc": _mean(risks),
            "coverage": len(automatic) / len(rows),
        }
    )
    base["metric_denominators"].update(
        {
            "scored_rows": len(rows),
            "candidate_set_recall_non_nil_gold_rows": len(candidate_recall_eligible),
            "selective_covered_rows": len(automatic),
        }
    )
    return {**base, "status": "ESTIMABLE"}


def read_jsonl_rows(path: str) -> tuple[ConfidenceEvaluationRow, ...]:
    """Strict, no-write JSONL reader used by the operator command wrapper."""

    parsed: list[ConfidenceEvaluationRow] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                raise ValueError(f"blank JSONL line: {line_number}")
            value = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs)
            if not isinstance(value, Mapping):
                raise ValueError(f"row {line_number} must be an object")
            probabilities = tuple(LabelProbability(**item) for item in value.get("event_probabilities", ()))
            raw_artifacts = value.get("evidence_artifacts", ())
            if not isinstance(raw_artifacts, (list, tuple)):
                raise ValueError(f"row {line_number} evidence_artifacts must be a list")
            artifacts = tuple(ArtifactRef(**item) for item in raw_artifacts)
            report = TypedConfidenceReport(
                post_id=value.get("post_id"),
                candidate_set_fingerprint=value.get("candidate_set_fingerprint"),
                producer_generation_status=value.get("producer_generation_status"),
                candidate_set_recall_status=value.get("candidate_set_recall_status"),
                event_probabilities=probabilities,
                probability_status=value.get("probability_status"),
                selected_label=value.get("selected_label"),
                selected_probability=value.get("selected_probability"),
                confidence_percentage=value.get("confidence_percentage"),
                shadow_action=value.get("shadow_action"),
                action_applied=value.get("action_applied"),
                operational_effect=value.get("operational_effect"),
                evidence_mode=value.get("evidence_mode"),
                evidence_artifacts=artifacts,
                schema_version=value.get("schema_version", SCHEMA_VERSION),
            )
            parsed.append(ConfidenceEvaluationRow(report=report, gold_label=value.get("gold_label")))
    return tuple(parsed)
