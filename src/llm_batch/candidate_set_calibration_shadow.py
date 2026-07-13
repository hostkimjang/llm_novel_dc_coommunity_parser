"""Artifact-bound CandidateSet/NIL probability calibration shadow contracts.

This module is intentionally a sibling of :mod:`candidate_set_shadow`.  The
P1 shadow remains an all-null observation contract.  P3 probabilities are
admissible only inside this additional envelope after a scorer, calibration
fit receipt, split manifest, and pre-registered evaluation policy are bound by
hash.  The envelope is always observational and never writes publication
fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

from .calibration_actual_readback import (
    cluster_bootstrap,
    validate_actual_readback_artifacts,
    validate_readback_manifest,
)

from .candidate_set_shadow import (
    NIL_LABEL,
    PROBABILITY_STATUS,
    SHADOW_ACTION_ABSTAIN,
    SHADOW_ACTION_ASSERT_NIL,
    SHADOW_ACTION_NOT_EVALUATED,
    SHADOW_ACTION_RESOLVE,
    SHADOW_OPERATIONAL_EFFECT,
    SelectiveShadowDecision,
)


CALIBRATION_SPLIT_MANIFEST_SCHEMA = "candidate_set_calibration_split_manifest_v1"
CALIBRATION_POLICY_SCHEMA = "candidate_set_calibration_policy_v2"
CALIBRATION_POLICY_SCHEMA_V3 = "candidate_set_calibration_policy_v3"
TOP_LABEL_DENOMINATOR_ALL_FROZEN_ROWS = "ALL_FROZEN_ROWS"
TOP_LABEL_DENOMINATOR_NON_ABSTAIN_ROWS = "NON_ABSTAIN_ROWS"
TOP_LABEL_DENOMINATOR_VALUES = frozenset(
    {
        TOP_LABEL_DENOMINATOR_ALL_FROZEN_ROWS,
        TOP_LABEL_DENOMINATOR_NON_ABSTAIN_ROWS,
    }
)
CALIBRATION_FIT_RECEIPT_SCHEMA = "candidate_set_calibration_fit_receipt_v1"
CALIBRATION_ARTIFACT_SCHEMA = "candidate_set_calibration_artifact_v1"
FROZEN_ACTUAL_EVIDENCE_SCHEMA = "candidate_set_frozen_actual_evidence_receipt_v2"
EVENT_SCORE_VECTOR_SCHEMA = "candidate_set_event_score_vector_v1"
CALIBRATION_SHADOW_SCHEMA = "candidate_set_calibration_shadow_v1"
CALIBRATION_UNAVAILABLE_SCHEMA = "candidate_set_calibration_unavailable_v1"
CALIBRATED_BOUND_STATUS = "CALIBRATED_SHADOW_BOUND"
PROBABILITY_SCALE = 1_000_000
CALIBRATION_SPLITS = ("DEV", "CALIBRATION", "FROZEN_HOLDOUT")
CALIBRATION_EVIDENCE_MODES = ("SYNTHETIC_CONTRACT_ONLY", "FROZEN_ACTUAL")
_SHA256_LENGTH = 64


def _canonical_payload(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _canonical_payload(value.to_dict())
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_payload(item) for item in value]
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        _canonical_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _require_sha256(value: Any, field_name: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != _SHA256_LENGTH or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError(f"{field_name} must be a sha256 hex digest")
    return text


def _strict_nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative int")
    return value


def _strict_probability(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be finite within [0, 1]")
    return number


def _strict_finite(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _sorted_unique(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(sorted({_require_text(value, "sequence value") for value in values}))


@dataclass(frozen=True)
class CalibrationSplitAssignment:
    example_id: str
    post_id: str
    split_group_id: str
    content_fingerprint: str
    source_group_fingerprint: str
    split: str
    truth_kind: str
    truth_label: Optional[str]
    label_provenance_sha256: str
    candidate_set_fingerprint: str
    gold_work_fingerprint: Optional[str]
    binding_status: str
    matched_candidate_ids: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name in ("example_id", "post_id", "split_group_id"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        for field_name in (
            "content_fingerprint",
            "source_group_fingerprint",
            "label_provenance_sha256",
            "candidate_set_fingerprint",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        if self.split not in CALIBRATION_SPLITS:
            raise ValueError("unsupported calibration split")
        if self.truth_kind not in {"CANDIDATE", "NIL", "UNJUDGED"}:
            raise ValueError("unsupported truth_kind")
        object.__setattr__(self, "matched_candidate_ids", tuple(self.matched_candidate_ids))
        if self.matched_candidate_ids != _sorted_unique(self.matched_candidate_ids):
            raise ValueError("matched_candidate_ids must be sorted and unique")
        if self.truth_kind == "CANDIDATE":
            object.__setattr__(
                self,
                "gold_work_fingerprint",
                _require_sha256(self.gold_work_fingerprint, "gold_work_fingerprint"),
            )
            if self.binding_status == "UNIQUE":
                truth = _require_text(self.truth_label, "truth_label")
                if truth == NIL_LABEL or self.matched_candidate_ids != (truth,):
                    raise ValueError("candidate truth requires a unique candidate-id binding")
            elif self.binding_status == "MISSING":
                if self.truth_label is not None or self.matched_candidate_ids:
                    raise ValueError("missing candidate binding must retain a null y")
            elif self.binding_status == "AMBIGUOUS":
                if self.truth_label is not None or len(self.matched_candidate_ids) < 2:
                    raise ValueError("ambiguous candidate binding must retain all competing ids")
            else:
                raise ValueError("candidate binding_status must be UNIQUE, MISSING, or AMBIGUOUS")
        elif self.truth_kind == "NIL":
            if self.gold_work_fingerprint is not None:
                raise ValueError("NIL truth must not bind a gold work")
            if self.truth_label != NIL_LABEL:
                raise ValueError("NIL truth must use the reserved NIL label")
            if self.binding_status != "NOT_APPLICABLE" or self.matched_candidate_ids:
                raise ValueError("NIL truth must not bind a work candidate")
        else:
            if self.gold_work_fingerprint is not None:
                object.__setattr__(
                    self,
                    "gold_work_fingerprint",
                    _require_sha256(self.gold_work_fingerprint, "gold_work_fingerprint"),
                )
            if self.truth_label is not None:
                raise ValueError("UNJUDGED truth_label must be null")
            if self.binding_status not in {"NOT_APPLICABLE", "MISSING", "AMBIGUOUS"}:
                raise ValueError("UNJUDGED binding_status is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "post_id": self.post_id,
            "split_group_id": self.split_group_id,
            "content_fingerprint": self.content_fingerprint,
            "source_group_fingerprint": self.source_group_fingerprint,
            "split": self.split,
            "truth_kind": self.truth_kind,
            "truth_label": self.truth_label,
            "label_provenance_sha256": self.label_provenance_sha256,
            "candidate_set_fingerprint": self.candidate_set_fingerprint,
            "gold_work_fingerprint": self.gold_work_fingerprint,
            "binding_status": self.binding_status,
            "matched_candidate_ids": list(self.matched_candidate_ids),
        }


@dataclass(frozen=True)
class CalibrationSplitManifest:
    assignments: Tuple[CalibrationSplitAssignment, ...]
    source_label_ledger_sha256: str
    assignment_seed_sha256: str
    split_fingerprints: Mapping[str, str]
    manifest_sha256: str
    schema_version: str = CALIBRATION_SPLIT_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", tuple(self.assignments))
        object.__setattr__(
            self,
            "source_label_ledger_sha256",
            _require_sha256(self.source_label_ledger_sha256, "source_label_ledger_sha256"),
        )
        object.__setattr__(
            self,
            "assignment_seed_sha256",
            _require_sha256(self.assignment_seed_sha256, "assignment_seed_sha256"),
        )
        if self.schema_version != CALIBRATION_SPLIT_MANIFEST_SCHEMA:
            raise ValueError("unsupported split manifest schema")
        if not self.assignments:
            raise ValueError("split manifest must contain assignments")
        example_ids = [item.example_id for item in self.assignments]
        post_ids = [item.post_id for item in self.assignments]
        if len(example_ids) != len(set(example_ids)):
            raise ValueError("duplicate example_id in split manifest")
        if len(post_ids) != len(set(post_ids)):
            raise ValueError("duplicate post_id in split manifest")
        for split in CALIBRATION_SPLITS:
            if not any(item.split == split for item in self.assignments):
                raise ValueError(f"split manifest is missing {split}")
        self._assert_no_cross_split_leakage("split_group_id", "split-group leakage")
        self._assert_no_cross_split_leakage("content_fingerprint", "content leakage")
        self._assert_no_cross_split_leakage("source_group_fingerprint", "source-group leakage")
        self._assert_no_cross_split_leakage(
            "candidate_set_fingerprint", "candidate-set leakage"
        )
        candidate_split: dict[str, str] = {}
        for item in self.assignments:
            if item.gold_work_fingerprint is not None:
                previous = candidate_split.setdefault(item.gold_work_fingerprint, item.split)
                if previous != item.split:
                    raise ValueError("candidate/work leakage")
            for candidate_id in item.matched_candidate_ids:
                previous = candidate_split.setdefault(candidate_id, item.split)
                if previous != item.split:
                    raise ValueError("candidate/work leakage")
        stored = dict(self.split_fingerprints)
        if set(stored) != set(CALIBRATION_SPLITS):
            raise ValueError("split_fingerprints keys mismatch")
        expected = self._compute_split_fingerprints(self.assignments)
        if stored != expected:
            raise ValueError("split_fingerprints mismatch")
        _require_sha256(self.manifest_sha256, "manifest_sha256")
        if self.manifest_sha256 != _canonical_hash(self.payload_without_manifest_sha256()):
            raise ValueError("split manifest fingerprint mismatch")

    def _assert_no_cross_split_leakage(self, field_name: str, message: str) -> None:
        seen: dict[str, str] = {}
        for item in self.assignments:
            value = str(getattr(item, field_name))
            previous = seen.setdefault(value, item.split)
            if previous != item.split:
                raise ValueError(message)

    @staticmethod
    def _compute_split_fingerprints(
        assignments: Sequence[CalibrationSplitAssignment],
    ) -> dict[str, str]:
        return {
            split: _canonical_hash(
                [
                    item.to_dict()
                    for item in sorted(
                        (row for row in assignments if row.split == split),
                        key=lambda row: row.example_id,
                    )
                ]
            )
            for split in CALIBRATION_SPLITS
        }

    @classmethod
    def create(
        cls,
        *,
        assignments: Sequence[CalibrationSplitAssignment],
        source_label_ledger_sha256: str,
        assignment_seed_sha256: str,
    ) -> "CalibrationSplitManifest":
        rows = tuple(assignments)
        split_fingerprints = cls._compute_split_fingerprints(rows)
        payload = {
            "schema_version": CALIBRATION_SPLIT_MANIFEST_SCHEMA,
            "assignments": [item.to_dict() for item in rows],
            "source_label_ledger_sha256": source_label_ledger_sha256,
            "assignment_seed_sha256": assignment_seed_sha256,
            "split_fingerprints": split_fingerprints,
        }
        return cls(
            assignments=rows,
            source_label_ledger_sha256=source_label_ledger_sha256,
            assignment_seed_sha256=assignment_seed_sha256,
            split_fingerprints=split_fingerprints,
            manifest_sha256=_canonical_hash(payload),
        )

    def payload_without_manifest_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assignments": [item.to_dict() for item in self.assignments],
            "source_label_ledger_sha256": self.source_label_ledger_sha256,
            "assignment_seed_sha256": self.assignment_seed_sha256,
            "split_fingerprints": dict(self.split_fingerprints),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_manifest_sha256(), "manifest_sha256": self.manifest_sha256}


@dataclass(frozen=True)
class CalibrationEvaluationPolicy:
    fixed_bin_edges: Tuple[float, ...]
    selector_max_error_probability: float
    nil_min_probability: float
    alpha: float
    min_dev_rows: int
    min_dev_per_truth_class: int
    min_calibration_rows: int
    min_calibration_per_truth_class: int
    min_frozen_rows: int
    min_per_truth_class: int
    min_occupied_bin_rows: int
    target_coverage: float
    max_selective_risk_upper_bound: float
    baseline_noninferiority_margin: float
    min_candidate_recall_lower_bound: float
    min_nil_prediction_count: int
    min_nil_precision_lower_bound: float
    min_nil_recall_lower_bound: float
    paired_delta_ci_bounds: Mapping[str, float]
    policy_scope: str
    policy_origin: str
    policy_sha256: str
    schema_version: str = CALIBRATION_POLICY_SCHEMA
    top_label_accuracy_denominator: str = TOP_LABEL_DENOMINATOR_ALL_FROZEN_ROWS

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixed_bin_edges", tuple(float(value) for value in self.fixed_bin_edges))
        edges = self.fixed_bin_edges
        if len(edges) < 2 or edges[0] != 0.0 or edges[-1] != 1.0:
            raise ValueError("fixed_bin_edges must start at 0 and end at 1")
        if any(not math.isfinite(value) for value in edges) or any(
            left >= right for left, right in zip(edges, edges[1:])
        ):
            raise ValueError("fixed_bin_edges must be finite and strictly increasing")
        for field_name in (
            "selector_max_error_probability",
            "nil_min_probability",
            "target_coverage",
            "max_selective_risk_upper_bound",
            "baseline_noninferiority_margin",
            "min_candidate_recall_lower_bound",
            "min_nil_precision_lower_bound",
            "min_nil_recall_lower_bound",
        ):
            object.__setattr__(self, field_name, _strict_probability(getattr(self, field_name), field_name))
        if self.target_coverage <= 0.0:
            raise ValueError("target_coverage must be greater than zero")
        alpha = _strict_probability(self.alpha, "alpha")
        if not 0.0 < alpha < 0.5:
            raise ValueError("alpha must be within (0, 0.5)")
        object.__setattr__(self, "alpha", alpha)
        expected_delta_keys = {
            "top_label_accuracy",
            "brier",
            "log_loss",
            "ece",
            "selective_risk",
            "aurc",
        }
        if not isinstance(self.paired_delta_ci_bounds, Mapping) or set(
            self.paired_delta_ci_bounds
        ) != expected_delta_keys:
            raise ValueError("paired_delta_ci_bounds must contain the exact six metric keys")
        delta_bounds = {
            key: _strict_finite(value, f"paired_delta_ci_bounds.{key}")
            for key, value in self.paired_delta_ci_bounds.items()
        }
        if not -1.0 <= delta_bounds["top_label_accuracy"] <= 1.0:
            raise ValueError("top_label_accuracy paired lower bound must be within [-1, 1]")
        if any(
            delta_bounds[key] < 0.0
            for key in ("brier", "log_loss", "ece", "selective_risk", "aurc")
        ):
            raise ValueError("paired loss/risk upper bounds must be non-negative")
        if any(
            delta_bounds[key] > 1.0
            for key in ("ece", "selective_risk", "aurc")
        ):
            raise ValueError("paired probability/risk upper bounds must be within [0, 1]")
        if delta_bounds["selective_risk"] != self.baseline_noninferiority_margin:
            raise ValueError("paired selective-risk bound must match baseline_noninferiority_margin")
        object.__setattr__(
            self,
            "paired_delta_ci_bounds",
            MappingProxyType(dict(sorted(delta_bounds.items()))),
        )
        for field_name in (
            "min_frozen_rows",
            "min_per_truth_class",
            "min_occupied_bin_rows",
            "min_nil_prediction_count",
            "min_dev_rows",
            "min_dev_per_truth_class",
            "min_calibration_rows",
            "min_calibration_per_truth_class",
        ):
            value = _strict_nonnegative_int(getattr(self, field_name), field_name)
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.policy_origin != "PRE_REGISTERED_DEV_CALIBRATION":
            raise ValueError("policy_origin must be PRE_REGISTERED_DEV_CALIBRATION")
        if self.policy_scope not in {
            "SYNTHETIC_CONTRACT_ONLY",
            "FROZEN_ACTUAL_PRE_REGISTERED",
        }:
            raise ValueError("unsupported policy_scope")
        if self.policy_scope == "FROZEN_ACTUAL_PRE_REGISTERED" and any(
            value <= 0.0
            for value in (
                self.min_candidate_recall_lower_bound,
                self.min_nil_precision_lower_bound,
                self.min_nil_recall_lower_bound,
            )
        ):
            raise ValueError("actual frozen lower-bound thresholds must be positive")
        if self.schema_version not in {
            CALIBRATION_POLICY_SCHEMA,
            CALIBRATION_POLICY_SCHEMA_V3,
        }:
            raise ValueError("unsupported calibration policy schema")
        if self.top_label_accuracy_denominator not in TOP_LABEL_DENOMINATOR_VALUES:
            raise ValueError("unsupported top_label_accuracy_denominator")
        if (
            self.policy_scope == "FROZEN_ACTUAL_PRE_REGISTERED"
            and self.schema_version != CALIBRATION_POLICY_SCHEMA_V3
        ):
            raise ValueError(
                "FROZEN_ACTUAL policy requires explicit v3 top_label_accuracy denominator"
            )
        _require_sha256(self.policy_sha256, "policy_sha256")
        if self.policy_sha256 != _canonical_hash(self.payload_without_policy_sha256()):
            raise ValueError("calibration policy fingerprint mismatch")

    @classmethod
    def create(cls, **values: Any) -> "CalibrationEvaluationPolicy":
        values.setdefault(
            "schema_version",
            (
                CALIBRATION_POLICY_SCHEMA_V3
                if values.get("policy_scope") == "FROZEN_ACTUAL_PRE_REGISTERED"
                else CALIBRATION_POLICY_SCHEMA
            ),
        )
        values.setdefault(
            "top_label_accuracy_denominator",
            TOP_LABEL_DENOMINATOR_ALL_FROZEN_ROWS,
        )
        serialized_values = {
            key: list(value) if key == "fixed_bin_edges" else value
            for key, value in values.items()
            if not (
                key == "top_label_accuracy_denominator"
                and values["schema_version"] == CALIBRATION_POLICY_SCHEMA
            )
        }
        payload = {
            "schema_version": values["schema_version"],
            **serialized_values,
        }
        return cls(**values, policy_sha256=_canonical_hash(payload))

    def payload_without_policy_sha256(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "fixed_bin_edges": list(self.fixed_bin_edges),
            "selector_max_error_probability": self.selector_max_error_probability,
            "nil_min_probability": self.nil_min_probability,
            "alpha": self.alpha,
            "min_dev_rows": self.min_dev_rows,
            "min_dev_per_truth_class": self.min_dev_per_truth_class,
            "min_calibration_rows": self.min_calibration_rows,
            "min_calibration_per_truth_class": self.min_calibration_per_truth_class,
            "min_frozen_rows": self.min_frozen_rows,
            "min_per_truth_class": self.min_per_truth_class,
            "min_occupied_bin_rows": self.min_occupied_bin_rows,
            "target_coverage": self.target_coverage,
            "max_selective_risk_upper_bound": self.max_selective_risk_upper_bound,
            "baseline_noninferiority_margin": self.baseline_noninferiority_margin,
            "min_candidate_recall_lower_bound": self.min_candidate_recall_lower_bound,
            "min_nil_prediction_count": self.min_nil_prediction_count,
            "min_nil_precision_lower_bound": self.min_nil_precision_lower_bound,
            "min_nil_recall_lower_bound": self.min_nil_recall_lower_bound,
            "paired_delta_ci_bounds": dict(self.paired_delta_ci_bounds),
            "policy_scope": self.policy_scope,
            "policy_origin": self.policy_origin,
        }
        if self.schema_version == CALIBRATION_POLICY_SCHEMA_V3:
            payload["top_label_accuracy_denominator"] = (
                self.top_label_accuracy_denominator
            )
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_policy_sha256(), "policy_sha256": self.policy_sha256}


@dataclass(frozen=True)
class CalibrationFitReceipt:
    split_manifest_sha256: str
    calibration_split_fingerprint: str
    scorer_fingerprint: str
    fit_row_count: int
    candidate_truth_count: int
    resolved_candidate_count: int
    unresolved_candidate_count: int
    nil_truth_count: int
    unjudged_count: int
    method: str
    temperature: float
    receipt_sha256: str
    fit_split: str = "CALIBRATION"
    status: str = "VALID"
    schema_version: str = CALIBRATION_FIT_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        for field_name in (
            "split_manifest_sha256",
            "calibration_split_fingerprint",
            "scorer_fingerprint",
            "receipt_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_sha256(getattr(self, field_name), field_name),
            )
        for field_name in (
            "fit_row_count",
            "candidate_truth_count",
            "resolved_candidate_count",
            "unresolved_candidate_count",
            "nil_truth_count",
            "unjudged_count",
        ):
            _strict_nonnegative_int(getattr(self, field_name), field_name)
        if (
            self.fit_row_count
            != self.candidate_truth_count + self.nil_truth_count + self.unjudged_count
        ):
            raise ValueError("fit receipt truth counts do not sum to fit_row_count")
        if self.candidate_truth_count != self.resolved_candidate_count + self.unresolved_candidate_count:
            raise ValueError("fit receipt candidate binding counts mismatch")
        if self.unjudged_count != 0 or self.unresolved_candidate_count != 0:
            raise ValueError("calibration fit split must contain only resolved labels")
        if self.method != "TEMPERATURE_SCALING":
            raise ValueError("unsupported fit receipt method")
        temperature = _strict_finite(self.temperature, "temperature")
        if temperature <= 0.0:
            raise ValueError("fit receipt temperature must be positive")
        object.__setattr__(self, "temperature", temperature)
        if self.fit_split != "CALIBRATION" or self.status != "VALID":
            raise ValueError("calibration fit receipt status/split is invalid")
        if self.schema_version != CALIBRATION_FIT_RECEIPT_SCHEMA:
            raise ValueError("unsupported calibration fit receipt schema")

    @classmethod
    def create(cls, **values: Any) -> "CalibrationFitReceipt":
        payload = {
            "schema_version": CALIBRATION_FIT_RECEIPT_SCHEMA,
            "fit_split": "CALIBRATION",
            "status": "VALID",
            **values,
        }
        return cls(**values, receipt_sha256=_canonical_hash(payload))

    def payload_without_receipt_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "split_manifest_sha256": self.split_manifest_sha256,
            "calibration_split_fingerprint": self.calibration_split_fingerprint,
            "scorer_fingerprint": self.scorer_fingerprint,
            "fit_row_count": self.fit_row_count,
            "candidate_truth_count": self.candidate_truth_count,
            "resolved_candidate_count": self.resolved_candidate_count,
            "unresolved_candidate_count": self.unresolved_candidate_count,
            "nil_truth_count": self.nil_truth_count,
            "unjudged_count": self.unjudged_count,
            "method": self.method,
            "temperature": self.temperature,
            "fit_split": self.fit_split,
            "status": self.status,
        }

    def validate_against(
        self,
        split_manifest: CalibrationSplitManifest,
        policy: CalibrationEvaluationPolicy,
    ) -> None:
        if self.receipt_sha256 != _canonical_hash(self.payload_without_receipt_sha256()):
            raise ValueError("calibration fit receipt fingerprint mismatch")
        calibration_rows = [
            item
            for item in split_manifest.assignments
            if item.split == "CALIBRATION"
        ]
        counts = {
            kind: sum(item.truth_kind == kind for item in calibration_rows)
            for kind in ("CANDIDATE", "NIL", "UNJUDGED")
        }
        resolved_candidates = sum(
            item.truth_kind == "CANDIDATE"
            and item.binding_status == "UNIQUE"
            and item.truth_label is not None
            for item in calibration_rows
        )
        unresolved_candidates = counts["CANDIDATE"] - resolved_candidates
        if (
            self.split_manifest_sha256 != split_manifest.manifest_sha256
            or self.calibration_split_fingerprint
            != split_manifest.split_fingerprints["CALIBRATION"]
            or self.fit_row_count != len(calibration_rows)
            or self.candidate_truth_count != counts["CANDIDATE"]
            or self.resolved_candidate_count != resolved_candidates
            or self.unresolved_candidate_count != unresolved_candidates
            or self.nil_truth_count != counts["NIL"]
            or self.unjudged_count != counts["UNJUDGED"]
        ):
            raise ValueError("calibration fit receipt does not match the manifest")
        if self.fit_row_count < policy.min_calibration_rows or min(
            self.candidate_truth_count,
            self.nil_truth_count,
        ) < policy.min_calibration_per_truth_class:
            raise ValueError("calibration fit sample is below the pre-registered minimum")
        dev_rows = [item for item in split_manifest.assignments if item.split == "DEV"]
        dev_counts = {
            kind: sum(item.truth_kind == kind for item in dev_rows)
            for kind in ("CANDIDATE", "NIL")
        }
        dev_resolved_candidates = sum(
            item.truth_kind == "CANDIDATE"
            and item.binding_status == "UNIQUE"
            and item.truth_label is not None
            for item in dev_rows
        )
        if (
            any(item.truth_kind == "UNJUDGED" for item in dev_rows)
            or dev_resolved_candidates != dev_counts["CANDIDATE"]
        ):
            raise ValueError("DEV policy split must contain only resolved labels")
        if len(dev_rows) < policy.min_dev_rows or min(dev_counts.values()) < policy.min_dev_per_truth_class:
            raise ValueError("DEV sample is below the pre-registered minimum")

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_receipt_sha256(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True)
class CalibrationArtifact:
    split_manifest_sha256: str
    calibration_split_fingerprint: str
    frozen_holdout_fingerprint: str
    scorer_fingerprint: str
    policy_sha256: str
    fit_receipt: CalibrationFitReceipt
    method: str
    temperature: float
    artifact_sha256: str
    fit_split: str = "CALIBRATION"
    evaluation_split: str = "FROZEN_HOLDOUT"
    status: str = "VALID"
    schema_version: str = CALIBRATION_ARTIFACT_SCHEMA

    def __post_init__(self) -> None:
        for field_name in (
            "split_manifest_sha256",
            "calibration_split_fingerprint",
            "frozen_holdout_fingerprint",
            "scorer_fingerprint",
            "policy_sha256",
            "artifact_sha256",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        if self.method != "TEMPERATURE_SCALING":
            raise ValueError("unsupported calibration method")
        temperature = _strict_finite(self.temperature, "temperature")
        if temperature <= 0.0:
            raise ValueError("temperature must be positive")
        object.__setattr__(self, "temperature", temperature)
        if self.fit_split != "CALIBRATION" or self.evaluation_split != "FROZEN_HOLDOUT":
            raise ValueError("calibration artifact split roles are invalid")
        if self.status != "VALID" or self.schema_version != CALIBRATION_ARTIFACT_SCHEMA:
            raise ValueError("calibration artifact status/schema is invalid")
        if not isinstance(self.fit_receipt, CalibrationFitReceipt):
            raise ValueError("calibration artifact requires a typed fit receipt")
        if (
            self.fit_receipt.scorer_fingerprint != self.scorer_fingerprint
            or self.fit_receipt.method != self.method
            or self.fit_receipt.temperature != self.temperature
        ):
            raise ValueError("calibration artifact/fit receipt mismatch")

    @property
    def calibrator_fit_receipt_sha256(self) -> str:
        return self.fit_receipt.receipt_sha256

    @classmethod
    def create(cls, **values: Any) -> "CalibrationArtifact":
        payload = {
            "schema_version": CALIBRATION_ARTIFACT_SCHEMA,
            "fit_split": "CALIBRATION",
            "evaluation_split": "FROZEN_HOLDOUT",
            "status": "VALID",
            **values,
        }
        return cls(**values, artifact_sha256=_canonical_hash(payload))

    def payload_without_artifact_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "split_manifest_sha256": self.split_manifest_sha256,
            "calibration_split_fingerprint": self.calibration_split_fingerprint,
            "frozen_holdout_fingerprint": self.frozen_holdout_fingerprint,
            "scorer_fingerprint": self.scorer_fingerprint,
            "policy_sha256": self.policy_sha256,
            "fit_receipt": self.fit_receipt.to_dict(),
            "method": self.method,
            "temperature": self.temperature,
            "fit_split": self.fit_split,
            "evaluation_split": self.evaluation_split,
            "status": self.status,
        }

    def validate(self) -> None:
        if self.artifact_sha256 != _canonical_hash(self.payload_without_artifact_sha256()):
            raise ValueError("calibration artifact fingerprint mismatch")

    def validate_against(
        self,
        split_manifest: CalibrationSplitManifest,
        policy: CalibrationEvaluationPolicy,
    ) -> None:
        self.validate()
        self.fit_receipt.validate_against(split_manifest, policy)

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_artifact_sha256(), "artifact_sha256": self.artifact_sha256}


@dataclass(frozen=True)
class FrozenActualEvidenceReceipt:
    run_spec_sha256: str
    split_manifest_sha256: str
    source_label_ledger_sha256: str
    expected_universe_artifact_sha256: str
    prediction_artifact_sha256: str
    baseline_prediction_artifact_sha256: str
    producer_receipt_artifact_sha256: str
    readback_manifest_sha256: str
    evaluation_plan_sha256: str
    calibrator_fit_receipt_sha256: str
    baseline_calibrator_fit_receipt_sha256: str
    generation_proof_set_sha256: str
    metric_protocol_sha256: str
    receipt_sha256: str
    evidence_scope: str = "FROZEN_ACTUAL"
    schema_version: str = FROZEN_ACTUAL_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        for field_name in (
            "run_spec_sha256",
            "split_manifest_sha256",
            "source_label_ledger_sha256",
            "expected_universe_artifact_sha256",
            "prediction_artifact_sha256",
            "baseline_prediction_artifact_sha256",
            "producer_receipt_artifact_sha256",
            "readback_manifest_sha256",
            "evaluation_plan_sha256",
            "calibrator_fit_receipt_sha256",
            "baseline_calibrator_fit_receipt_sha256",
            "generation_proof_set_sha256",
            "metric_protocol_sha256",
            "receipt_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_sha256(getattr(self, field_name), field_name),
            )
        if self.evidence_scope != "FROZEN_ACTUAL":
            raise ValueError("frozen evidence scope mismatch")
        if self.schema_version != FROZEN_ACTUAL_EVIDENCE_SCHEMA:
            raise ValueError("unsupported frozen evidence receipt schema")

    @classmethod
    def create(cls, **values: Any) -> "FrozenActualEvidenceReceipt":
        payload = {
            "schema_version": FROZEN_ACTUAL_EVIDENCE_SCHEMA,
            "evidence_scope": "FROZEN_ACTUAL",
            **values,
        }
        return cls(**values, receipt_sha256=_canonical_hash(payload))

    def payload_without_receipt_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "run_spec_sha256": self.run_spec_sha256,
            "split_manifest_sha256": self.split_manifest_sha256,
            "source_label_ledger_sha256": self.source_label_ledger_sha256,
            "expected_universe_artifact_sha256": self.expected_universe_artifact_sha256,
            "prediction_artifact_sha256": self.prediction_artifact_sha256,
            "baseline_prediction_artifact_sha256": self.baseline_prediction_artifact_sha256,
            "producer_receipt_artifact_sha256": self.producer_receipt_artifact_sha256,
            "readback_manifest_sha256": self.readback_manifest_sha256,
            "evaluation_plan_sha256": self.evaluation_plan_sha256,
            "calibrator_fit_receipt_sha256": self.calibrator_fit_receipt_sha256,
            "baseline_calibrator_fit_receipt_sha256": self.baseline_calibrator_fit_receipt_sha256,
            "generation_proof_set_sha256": self.generation_proof_set_sha256,
            "metric_protocol_sha256": self.metric_protocol_sha256,
        }

    def validate(self) -> None:
        if self.receipt_sha256 != _canonical_hash(self.payload_without_receipt_sha256()):
            raise ValueError("frozen evidence receipt fingerprint mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_receipt_sha256(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True)
class EventScoreVector:
    example_id: str
    post_id: str
    split: str
    base_shadow_fingerprint: str
    candidate_set_fingerprint: str
    observation_fingerprint: str
    labels: Tuple[str, ...]
    raw_scores: Tuple[float, ...]
    scorer_fingerprint: str
    split_manifest_sha256: str
    generation_proof_fingerprint: str
    retrieval_state_fingerprint: str
    publication_input_fingerprint: str
    feature_schema_version: str
    feature_fingerprint: str
    score_vector_sha256: str
    schema_version: str = EVENT_SCORE_VECTOR_SCHEMA

    def __post_init__(self) -> None:
        for field_name in ("example_id", "post_id", "feature_schema_version"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        if self.split != "FROZEN_HOLDOUT":
            raise ValueError("score vector must target FROZEN_HOLDOUT")
        for field_name in (
            "base_shadow_fingerprint",
            "candidate_set_fingerprint",
            "observation_fingerprint",
            "scorer_fingerprint",
            "split_manifest_sha256",
            "generation_proof_fingerprint",
            "retrieval_state_fingerprint",
            "publication_input_fingerprint",
            "feature_fingerprint",
            "score_vector_sha256",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        object.__setattr__(self, "labels", tuple(self.labels))
        object.__setattr__(self, "raw_scores", tuple(_strict_finite(v, "raw_score") for v in self.raw_scores))
        if not self.labels or len(self.labels) != len(self.raw_scores):
            raise ValueError("score labels/raw_scores length mismatch")
        if len(self.labels) != len(set(self.labels)) or self.labels[-1] != NIL_LABEL:
            raise ValueError("score labels must be unique and end with NIL")
        if self.schema_version != EVENT_SCORE_VECTOR_SCHEMA:
            raise ValueError("unsupported score vector schema")

    @classmethod
    def create(
        cls,
        *,
        example_id: str,
        post_id: str,
        split: str,
        base_shadow: SelectiveShadowDecision,
        raw_scores: Sequence[float],
        scorer_fingerprint: str,
        split_manifest_sha256: str,
        generation_proof_fingerprint: str,
        retrieval_state_fingerprint: str,
        feature_schema_version: str,
        feature_fingerprint: str,
    ) -> "EventScoreVector":
        labels = tuple(item.label for item in base_shadow.event_probabilities)
        payload = {
            "schema_version": EVENT_SCORE_VECTOR_SCHEMA,
            "example_id": example_id,
            "post_id": str(post_id),
            "split": split,
            "base_shadow_fingerprint": base_shadow.shadow_fingerprint,
            "candidate_set_fingerprint": base_shadow.candidate_set.candidate_set_fingerprint,
            "observation_fingerprint": base_shadow.candidate_set.observation_fingerprint,
            "labels": list(labels),
            "raw_scores": [float(value) for value in raw_scores],
            "scorer_fingerprint": scorer_fingerprint,
            "split_manifest_sha256": split_manifest_sha256,
            "generation_proof_fingerprint": generation_proof_fingerprint,
            "retrieval_state_fingerprint": retrieval_state_fingerprint,
            "publication_input_fingerprint": base_shadow.input_fingerprint,
            "feature_schema_version": feature_schema_version,
            "feature_fingerprint": feature_fingerprint,
        }
        return cls(
            example_id=example_id,
            post_id=str(post_id),
            split=split,
            base_shadow_fingerprint=base_shadow.shadow_fingerprint,
            candidate_set_fingerprint=base_shadow.candidate_set.candidate_set_fingerprint,
            observation_fingerprint=base_shadow.candidate_set.observation_fingerprint,
            labels=labels,
            raw_scores=tuple(float(value) for value in raw_scores),
            scorer_fingerprint=scorer_fingerprint,
            split_manifest_sha256=split_manifest_sha256,
            generation_proof_fingerprint=generation_proof_fingerprint,
            retrieval_state_fingerprint=retrieval_state_fingerprint,
            publication_input_fingerprint=base_shadow.input_fingerprint,
            feature_schema_version=feature_schema_version,
            feature_fingerprint=feature_fingerprint,
            score_vector_sha256=_canonical_hash(payload),
        )

    def payload_without_score_vector_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "example_id": self.example_id,
            "post_id": self.post_id,
            "split": self.split,
            "base_shadow_fingerprint": self.base_shadow_fingerprint,
            "candidate_set_fingerprint": self.candidate_set_fingerprint,
            "observation_fingerprint": self.observation_fingerprint,
            "labels": list(self.labels),
            "raw_scores": list(self.raw_scores),
            "scorer_fingerprint": self.scorer_fingerprint,
            "split_manifest_sha256": self.split_manifest_sha256,
            "generation_proof_fingerprint": self.generation_proof_fingerprint,
            "retrieval_state_fingerprint": self.retrieval_state_fingerprint,
            "publication_input_fingerprint": self.publication_input_fingerprint,
            "feature_schema_version": self.feature_schema_version,
            "feature_fingerprint": self.feature_fingerprint,
        }

    def validate(self) -> None:
        if self.score_vector_sha256 != _canonical_hash(self.payload_without_score_vector_sha256()):
            raise ValueError("score vector fingerprint mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_score_vector_sha256(), "score_vector_sha256": self.score_vector_sha256}


@dataclass(frozen=True)
class CalibrationEventProbability:
    label: str
    probability_mass: Optional[int]
    probability_scale: int = PROBABILITY_SCALE

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _require_text(self.label, "probability label"))
        if self.probability_scale != PROBABILITY_SCALE:
            raise ValueError("probability_scale mismatch")
        if self.probability_mass is not None:
            value = _strict_nonnegative_int(self.probability_mass, "probability_mass")
            if value > self.probability_scale:
                raise ValueError("probability_mass exceeds probability_scale")

    @property
    def probability(self) -> Optional[float]:
        return None if self.probability_mass is None else self.probability_mass / self.probability_scale

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "probability_mass": self.probability_mass,
            "probability_scale": self.probability_scale,
        }


@dataclass(frozen=True)
class CalibrationShadow:
    example_id: str
    post_id: str
    base_shadow_fingerprint: str
    candidate_set_fingerprint: str
    observation_fingerprint: str
    generation_status: str
    candidate_set_recall_status: str
    event_probabilities: Tuple[CalibrationEventProbability, ...]
    probability_status: str
    selected_label: Optional[str]
    selected_error_probability_mass: Optional[int]
    action: str
    action_applied: bool
    operational_effect: str
    reason_codes: Tuple[str, ...]
    calibration_artifact_sha256: Optional[str]
    policy_sha256: Optional[str]
    split_manifest_sha256: Optional[str]
    score_vector_sha256: Optional[str]
    generation_proof_fingerprint: Optional[str]
    retrieval_state_fingerprint: Optional[str]
    publication_input_fingerprint: Optional[str]
    feature_fingerprint: Optional[str]
    shadow_fingerprint: str
    schema_version: str

    def __post_init__(self) -> None:
        for field_name in ("example_id", "post_id"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        for field_name in (
            "base_shadow_fingerprint",
            "candidate_set_fingerprint",
            "observation_fingerprint",
            "shadow_fingerprint",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        object.__setattr__(self, "event_probabilities", tuple(self.event_probabilities))
        object.__setattr__(self, "reason_codes", _sorted_unique(self.reason_codes))
        labels = [item.label for item in self.event_probabilities]
        if not labels or labels[-1] != NIL_LABEL or len(labels) != len(set(labels)):
            raise ValueError("calibration shadow labels must be unique and end with NIL")
        if self.action_applied is not False or self.operational_effect != SHADOW_OPERATIONAL_EFFECT:
            raise ValueError("calibration shadow must have no publication effect")
        if self.schema_version == CALIBRATION_UNAVAILABLE_SCHEMA:
            if self.probability_status != PROBABILITY_STATUS:
                raise ValueError("unavailable calibration shadow status mismatch")
            if any(item.probability_mass is not None for item in self.event_probabilities):
                raise ValueError("unavailable calibration probabilities must be all null")
            if self.selected_label is not None or self.selected_error_probability_mass is not None:
                raise ValueError("unavailable calibration shadow must not select a label")
            if any(
                value is not None
                for value in (
                    self.calibration_artifact_sha256,
                    self.policy_sha256,
                    self.split_manifest_sha256,
                    self.score_vector_sha256,
                    self.generation_proof_fingerprint,
                    self.retrieval_state_fingerprint,
                    self.publication_input_fingerprint,
                    self.feature_fingerprint,
                )
            ):
                raise ValueError("unavailable calibration shadow must not bind numeric artifacts")
            if self.action not in {SHADOW_ACTION_NOT_EVALUATED, SHADOW_ACTION_ABSTAIN}:
                raise ValueError("unavailable calibration shadow action mismatch")
        elif self.schema_version == CALIBRATION_SHADOW_SCHEMA:
            if self.probability_status != CALIBRATED_BOUND_STATUS:
                raise ValueError("bound calibration status mismatch")
            masses = [item.probability_mass for item in self.event_probabilities]
            if any(value is None for value in masses) or sum(int(value) for value in masses) != PROBABILITY_SCALE:
                raise ValueError("bound probability masses must exactly sum to probability_scale")
            if self.selected_label not in labels:
                raise ValueError("bound calibration selected_label is invalid")
            if self.selected_error_probability_mass is None:
                raise ValueError("bound calibration shadow requires selected error mass")
            selected_mass = next(
                int(item.probability_mass)
                for item in self.event_probabilities
                if item.label == self.selected_label
            )
            if self.selected_error_probability_mass != PROBABILITY_SCALE - selected_mass:
                raise ValueError("selected error mass mismatch")
            expected_selected_index = max(
                range(len(masses)),
                key=lambda index: (int(masses[index]), -index),
            )
            if self.selected_label != labels[expected_selected_index]:
                raise ValueError("selected_label must follow the frozen argmax tie policy")
            if self.action not in {
                SHADOW_ACTION_RESOLVE,
                SHADOW_ACTION_ASSERT_NIL,
                SHADOW_ACTION_ABSTAIN,
            }:
                raise ValueError("bound calibration action mismatch")
            if self.action == SHADOW_ACTION_RESOLVE and self.selected_label == NIL_LABEL:
                raise ValueError("RESOLVE requires a work-candidate label")
            if self.action == SHADOW_ACTION_ASSERT_NIL and self.selected_label != NIL_LABEL:
                raise ValueError("ASSERT_NIL requires the NIL label")
            hard_blockers = {
                "retrieval_failclose_requires_abstain",
                "candidate_set_integrity_requires_abstain",
            }.intersection(self.reason_codes)
            if hard_blockers and self.action != SHADOW_ACTION_ABSTAIN:
                raise ValueError("deterministic hard blockers require ABSTAIN")
            if self.action == SHADOW_ACTION_ABSTAIN and not {
                "retrieval_failclose_requires_abstain",
                "candidate_set_integrity_requires_abstain",
                "selective_risk_threshold_requires_abstain",
                "nil_threshold_requires_abstain",
            }.intersection(self.reason_codes):
                raise ValueError("ABSTAIN requires a bound blocker reason")
            for field_name in (
                "calibration_artifact_sha256",
                "policy_sha256",
                "split_manifest_sha256",
                "score_vector_sha256",
                "generation_proof_fingerprint",
                "retrieval_state_fingerprint",
                "publication_input_fingerprint",
                "feature_fingerprint",
            ):
                _require_sha256(getattr(self, field_name), field_name)
        else:
            raise ValueError("unsupported calibration shadow schema")
        if self.shadow_fingerprint != _canonical_hash(self.payload_without_shadow_fingerprint()):
            raise ValueError("calibration shadow fingerprint mismatch")

    def payload_without_shadow_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "example_id": self.example_id,
            "post_id": self.post_id,
            "base_shadow_fingerprint": self.base_shadow_fingerprint,
            "candidate_set_fingerprint": self.candidate_set_fingerprint,
            "observation_fingerprint": self.observation_fingerprint,
            "generation_status": self.generation_status,
            "candidate_set_recall_status": self.candidate_set_recall_status,
            "event_probabilities": [item.to_dict() for item in self.event_probabilities],
            "probability_status": self.probability_status,
            "selected_label": self.selected_label,
            "selected_error_probability_mass": self.selected_error_probability_mass,
            "action": self.action,
            "action_applied": self.action_applied,
            "operational_effect": self.operational_effect,
            "reason_codes": list(self.reason_codes),
            "calibration_artifact_sha256": self.calibration_artifact_sha256,
            "policy_sha256": self.policy_sha256,
            "split_manifest_sha256": self.split_manifest_sha256,
            "score_vector_sha256": self.score_vector_sha256,
            "generation_proof_fingerprint": self.generation_proof_fingerprint,
            "retrieval_state_fingerprint": self.retrieval_state_fingerprint,
            "publication_input_fingerprint": self.publication_input_fingerprint,
            "feature_fingerprint": self.feature_fingerprint,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_shadow_fingerprint(), "shadow_fingerprint": self.shadow_fingerprint}


def _make_shadow(payload: dict[str, Any]) -> CalibrationShadow:
    return CalibrationShadow(**payload, shadow_fingerprint=_canonical_hash(payload))


def _unavailable_shadow(
    base_shadow: SelectiveShadowDecision,
    *,
    score_vector: Optional[EventScoreVector],
    reason_code: str,
) -> CalibrationShadow:
    reasons = set(base_shadow.reason_codes)
    reasons.add(reason_code)
    reasons.add("probability_not_available")
    action = (
        SHADOW_ACTION_ABSTAIN
        if base_shadow.action == SHADOW_ACTION_ABSTAIN
        else SHADOW_ACTION_NOT_EVALUATED
    )
    payload = {
        "schema_version": CALIBRATION_UNAVAILABLE_SCHEMA,
        "example_id": score_vector.example_id if score_vector is not None else "UNBOUND",
        "post_id": score_vector.post_id if score_vector is not None else "UNBOUND",
        "base_shadow_fingerprint": base_shadow.shadow_fingerprint,
        "candidate_set_fingerprint": base_shadow.candidate_set.candidate_set_fingerprint,
        "observation_fingerprint": base_shadow.candidate_set.observation_fingerprint,
        "generation_status": base_shadow.candidate_set.generation_status,
        "candidate_set_recall_status": base_shadow.candidate_set.candidate_set_recall_status,
        "event_probabilities": tuple(
            CalibrationEventProbability(label=item.label, probability_mass=None)
            for item in base_shadow.event_probabilities
        ),
        "probability_status": PROBABILITY_STATUS,
        "selected_label": None,
        "selected_error_probability_mass": None,
        "action": action,
        "action_applied": False,
        "operational_effect": SHADOW_OPERATIONAL_EFFECT,
        "reason_codes": _sorted_unique(reasons),
        "calibration_artifact_sha256": None,
        "policy_sha256": None,
        "split_manifest_sha256": None,
        "score_vector_sha256": None,
        "generation_proof_fingerprint": None,
        "retrieval_state_fingerprint": None,
        "publication_input_fingerprint": None,
        "feature_fingerprint": None,
    }
    return _make_shadow(payload)


def _probability_masses(raw_scores: Sequence[float], temperature: float) -> Tuple[int, ...]:
    scaled = [float(value) / temperature for value in raw_scores]
    maximum = max(scaled)
    weights = [math.exp(value - maximum) for value in scaled]
    total = sum(weights)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("softmax weights are invalid")
    exact = [weight / total * PROBABILITY_SCALE for weight in weights]
    masses = [int(math.floor(value)) for value in exact]
    remainder = PROBABILITY_SCALE - sum(masses)
    order = sorted(range(len(exact)), key=lambda index: (-(exact[index] - masses[index]), index))
    for index in order[:remainder]:
        masses[index] += 1
    if sum(masses) != PROBABILITY_SCALE:
        raise ValueError("probability mass allocation failed")
    return tuple(masses)


def build_calibration_shadow(
    base_shadow: SelectiveShadowDecision,
    score_vector: Optional[EventScoreVector],
    artifact: Optional[CalibrationArtifact],
    policy: CalibrationEvaluationPolicy,
    *,
    split_manifest: Optional[CalibrationSplitManifest] = None,
    assignment: Optional[CalibrationSplitAssignment] = None,
) -> CalibrationShadow:
    if base_shadow.candidate_set.generation_status != "COMPLETE":
        return _unavailable_shadow(
            base_shadow,
            score_vector=score_vector,
            reason_code="candidate_set_generation_not_complete",
        )
    if base_shadow.candidate_set.candidate_set_recall_status != "READY_FOR_GOLD_EVALUATION":
        return _unavailable_shadow(
            base_shadow,
            score_vector=score_vector,
            reason_code="candidate_set_recall_not_ready",
        )
    if base_shadow.candidate_set.integrity_status != "GO":
        return _unavailable_shadow(
            base_shadow,
            score_vector=score_vector,
            reason_code="candidate_set_integrity_no_go",
        )
    if artifact is None:
        return _unavailable_shadow(
            base_shadow,
            score_vector=score_vector,
            reason_code="calibration_artifact_missing",
        )
    if score_vector is None:
        return _unavailable_shadow(
            base_shadow,
            score_vector=None,
            reason_code="event_score_vector_missing",
        )
    if split_manifest is None or assignment is None:
        return _unavailable_shadow(
            base_shadow,
            score_vector=score_vector,
            reason_code="split_assignment_binding_missing",
        )
    if artifact.split_manifest_sha256 != split_manifest.manifest_sha256:
        raise ValueError("calibration artifact split manifest binding mismatch")
    if (
        artifact.calibration_split_fingerprint
        != split_manifest.split_fingerprints["CALIBRATION"]
        or artifact.frozen_holdout_fingerprint
        != split_manifest.split_fingerprints["FROZEN_HOLDOUT"]
    ):
        raise ValueError("calibration artifact split fingerprints mismatch")
    stored_assignment = next(
        (
            item
            for item in split_manifest.assignments
            if item.example_id == assignment.example_id
        ),
        None,
    )
    if stored_assignment is None or stored_assignment.to_dict() != assignment.to_dict():
        raise ValueError("calibration assignment is not exactly bound to the split manifest")
    if assignment.split != "FROZEN_HOLDOUT":
        raise ValueError("calibration shadow may only target FROZEN_HOLDOUT")
    if score_vector.example_id != assignment.example_id or score_vector.post_id != assignment.post_id:
        raise ValueError("score vector does not match the frozen assignment")
    if assignment.candidate_set_fingerprint != base_shadow.candidate_set.candidate_set_fingerprint:
        raise ValueError("assignment candidate-set fingerprint mismatch")
    expected_labels = tuple(item.label for item in base_shadow.event_probabilities)
    if score_vector.labels != expected_labels:
        raise ValueError("score labels do not match base candidate/NIL event space")
    if score_vector.candidate_set_fingerprint != base_shadow.candidate_set.candidate_set_fingerprint:
        raise ValueError("score candidate-set fingerprint mismatch")
    if score_vector.observation_fingerprint != base_shadow.candidate_set.observation_fingerprint:
        raise ValueError("score observation fingerprint mismatch")
    if score_vector.base_shadow_fingerprint != base_shadow.shadow_fingerprint:
        raise ValueError("score base-shadow fingerprint mismatch")
    if score_vector.publication_input_fingerprint != base_shadow.input_fingerprint:
        raise ValueError("score publication-input fingerprint mismatch")
    if artifact.policy_sha256 != policy.policy_sha256:
        raise ValueError("calibration artifact policy binding mismatch")
    if score_vector.split_manifest_sha256 != artifact.split_manifest_sha256:
        raise ValueError("score split manifest binding mismatch")
    if score_vector.scorer_fingerprint != artifact.scorer_fingerprint:
        raise ValueError("score/scorer artifact binding mismatch")
    artifact.validate_against(split_manifest, policy)
    score_vector.validate()
    masses = _probability_masses(score_vector.raw_scores, artifact.temperature)
    selected_index = max(range(len(masses)), key=lambda index: (masses[index], -index))
    selected_label = expected_labels[selected_index]
    selected_error_mass = PROBABILITY_SCALE - masses[selected_index]
    selected_error = selected_error_mass / PROBABILITY_SCALE
    reasons = {
        "calibration_artifact_bound",
        "probability_mass_exact",
        "shadow_action_not_applied",
    }
    hard_blockers = {
        "retrieval_failclose_requires_abstain",
        "candidate_set_integrity_requires_abstain",
    }.intersection(base_shadow.reason_codes)
    reasons.update(hard_blockers)
    if hard_blockers:
        action = SHADOW_ACTION_ABSTAIN
    elif selected_error > policy.selector_max_error_probability:
        action = SHADOW_ACTION_ABSTAIN
        reasons.add("selective_risk_threshold_requires_abstain")
    elif selected_label == NIL_LABEL and masses[selected_index] / PROBABILITY_SCALE < policy.nil_min_probability:
        action = SHADOW_ACTION_ABSTAIN
        reasons.add("nil_threshold_requires_abstain")
    elif selected_label == NIL_LABEL:
        action = SHADOW_ACTION_ASSERT_NIL
    else:
        action = SHADOW_ACTION_RESOLVE
    payload = {
        "schema_version": CALIBRATION_SHADOW_SCHEMA,
        "example_id": score_vector.example_id,
        "post_id": score_vector.post_id,
        "base_shadow_fingerprint": base_shadow.shadow_fingerprint,
        "candidate_set_fingerprint": base_shadow.candidate_set.candidate_set_fingerprint,
        "observation_fingerprint": base_shadow.candidate_set.observation_fingerprint,
        "generation_status": base_shadow.candidate_set.generation_status,
        "candidate_set_recall_status": base_shadow.candidate_set.candidate_set_recall_status,
        "event_probabilities": tuple(
            CalibrationEventProbability(label=label, probability_mass=mass)
            for label, mass in zip(expected_labels, masses)
        ),
        "probability_status": CALIBRATED_BOUND_STATUS,
        "selected_label": selected_label,
        "selected_error_probability_mass": selected_error_mass,
        "action": action,
        "action_applied": False,
        "operational_effect": SHADOW_OPERATIONAL_EFFECT,
        "reason_codes": _sorted_unique(reasons),
        "calibration_artifact_sha256": artifact.artifact_sha256,
        "policy_sha256": policy.policy_sha256,
        "split_manifest_sha256": artifact.split_manifest_sha256,
        "score_vector_sha256": score_vector.score_vector_sha256,
        "generation_proof_fingerprint": score_vector.generation_proof_fingerprint,
        "retrieval_state_fingerprint": score_vector.retrieval_state_fingerprint,
        "publication_input_fingerprint": score_vector.publication_input_fingerprint,
        "feature_fingerprint": score_vector.feature_fingerprint,
    }
    return _make_shadow(payload)


def calibration_shadow_from_dict(value: Any) -> CalibrationShadow:
    if not isinstance(value, Mapping):
        raise ValueError("calibration shadow payload must be an object")
    probabilities = value.get("event_probabilities")
    if not isinstance(probabilities, list):
        raise ValueError("calibration shadow probabilities must be a list")
    return CalibrationShadow(
        example_id=value.get("example_id"),
        post_id=value.get("post_id"),
        base_shadow_fingerprint=value.get("base_shadow_fingerprint"),
        candidate_set_fingerprint=value.get("candidate_set_fingerprint"),
        observation_fingerprint=value.get("observation_fingerprint"),
        generation_status=value.get("generation_status"),
        candidate_set_recall_status=value.get("candidate_set_recall_status"),
        event_probabilities=tuple(
            CalibrationEventProbability(
                label=item.get("label"),
                probability_mass=item.get("probability_mass"),
                probability_scale=item.get("probability_scale"),
            )
            for item in probabilities
            if isinstance(item, Mapping)
        ),
        probability_status=value.get("probability_status"),
        selected_label=value.get("selected_label"),
        selected_error_probability_mass=value.get("selected_error_probability_mass"),
        action=value.get("action"),
        action_applied=value.get("action_applied"),
        operational_effect=value.get("operational_effect"),
        reason_codes=tuple(value.get("reason_codes") or ()),
        calibration_artifact_sha256=value.get("calibration_artifact_sha256"),
        policy_sha256=value.get("policy_sha256"),
        split_manifest_sha256=value.get("split_manifest_sha256"),
        score_vector_sha256=value.get("score_vector_sha256"),
        generation_proof_fingerprint=value.get("generation_proof_fingerprint"),
        retrieval_state_fingerprint=value.get("retrieval_state_fingerprint"),
        publication_input_fingerprint=value.get("publication_input_fingerprint"),
        feature_fingerprint=value.get("feature_fingerprint"),
        shadow_fingerprint=value.get("shadow_fingerprint"),
        schema_version=value.get("schema_version"),
    )


_METRIC_NAMES = (
    "top_label_accuracy",
    "multiclass_brier",
    "log_loss",
    "top_label_ece",
    "nil_precision",
    "nil_recall",
    "coverage",
    "selective_risk",
    "selective_risk_upper_bound",
    "target_coverage_achieved",
    "target_selective_risk",
    "target_selective_risk_upper_bound",
    "aurc",
)


def _null_metrics() -> dict[str, None]:
    return {name: None for name in _METRIC_NAMES}


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    maximum_iterations = 300
    epsilon = 3.0e-14
    floor = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < floor:
        d = floor
    d = 1.0 / d
    result = d
    for iteration in range(1, maximum_iterations + 1):
        twice = 2 * iteration
        numerator = iteration * (b - iteration) * x / (
            (qam + twice) * (a + twice)
        )
        d = 1.0 + numerator * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + numerator / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        result *= d * c
        numerator = -(a + iteration) * (qab + iteration) * x / (
            (a + twice) * (qap + twice)
        )
        d = 1.0 + numerator * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + numerator / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) < epsilon:
            return result
    raise ArithmeticError("incomplete beta continued fraction did not converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_quantile(probability: float, a: float, b: float) -> float:
    if probability <= 0.0:
        return 0.0
    if probability >= 1.0:
        return 1.0
    lower, upper = 0.0, 1.0
    for _ in range(160):
        midpoint = (lower + upper) / 2.0
        if _regularized_beta(midpoint, a, b) < probability:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _clopper_pearson_interval(successes: int, total: int, alpha: float, *, one_sided: bool = False) -> tuple[Optional[float], Optional[float]]:
    if total <= 0:
        return None, None
    tail = alpha if one_sided else alpha / 2.0
    lower = (
        0.0
        if successes == 0
        else _beta_quantile(tail, successes, total - successes + 1)
    )
    upper = (
        1.0
        if successes == total
        else _beta_quantile(1.0 - tail, successes + 1, total - successes)
    )
    return lower, upper


def _early_evaluation(
    *,
    status: str,
    reason: str,
    frozen_count: int,
    candidate_recall: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "schema_version": "candidate_set_calibration_evaluation_v1",
        "status": status,
        "reason": reason,
        "frozen_count": frozen_count,
        "candidate_set_recall": candidate_recall or {
            "value": None,
            "numerator": None,
            "denominator": None,
            "lower_bound": None,
        },
        "metrics": _null_metrics(),
        "intervals": {},
        "ece_bins": [],
        "conversion_allowed": False,
        "conversion_reason": reason,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }


def _bin_index(confidence: float, edges: Sequence[float]) -> int:
    if confidence == 1.0:
        return len(edges) - 2
    for index, (left, right) in enumerate(zip(edges, edges[1:])):
        if left <= confidence < right:
            return index
    raise ValueError("confidence is outside fixed ECE bins")


def _metric_bundle(
    assignments: Sequence[CalibrationSplitAssignment],
    shadows: Mapping[str, CalibrationShadow],
    policy: CalibrationEvaluationPolicy,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for assignment in assignments:
        shadow = shadows[assignment.example_id]
        probabilities = {item.label: float(item.probability) for item in shadow.event_probabilities}
        truth = str(assignment.truth_label)
        truth_probability = probabilities[truth]
        if truth_probability <= 0.0:
            raise ArithmeticError("LOGLOSS_INVALID_ZERO_TRUTH_PROBABILITY")
        selected = str(shadow.selected_label)
        confidence = probabilities[selected]
        correct = selected == truth
        brier = sum(
            (probability - (1.0 if label == truth else 0.0)) ** 2
            for label, probability in probabilities.items()
        )
        rows.append(
            {
                "example_id": assignment.example_id,
                "truth": truth,
                "selected": selected,
                "confidence": confidence,
                "correct": correct,
                "brier": brier,
                "log_loss": -math.log(truth_probability),
                "action": shadow.action,
                "risk_score": shadow.selected_error_probability_mass / PROBABILITY_SCALE,
            }
        )
    count = len(rows)
    bins: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(policy.fixed_bin_edges, policy.fixed_bin_edges[1:])):
        members = [row for row in rows if _bin_index(row["confidence"], policy.fixed_bin_edges) == index]
        if not members:
            bins.append({"left": left, "right": right, "count": 0, "mean_confidence": None, "accuracy": None, "gap": None})
            continue
        mean_confidence = sum(row["confidence"] for row in members) / len(members)
        accuracy = sum(row["correct"] for row in members) / len(members)
        bins.append({"left": left, "right": right, "count": len(members), "mean_confidence": mean_confidence, "accuracy": accuracy, "gap": abs(mean_confidence - accuracy)})
    ece = sum(item["count"] / count * item["gap"] for item in bins if item["count"])
    nil_predicted = [row for row in rows if row["action"] == SHADOW_ACTION_ASSERT_NIL]
    true_nil = [row for row in rows if row["truth"] == NIL_LABEL]
    true_positive = sum(row["truth"] == NIL_LABEL for row in nil_predicted)
    false_positive = len(nil_predicted) - true_positive
    false_negative = sum(row["action"] != SHADOW_ACTION_ASSERT_NIL for row in true_nil)
    nil_precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else None
    nil_recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else None
    covered = [row for row in rows if row["action"] != SHADOW_ACTION_ABSTAIN]
    errors = sum(not row["correct"] for row in covered)
    coverage = len(covered) / count
    selective_risk = errors / len(covered) if covered else None
    _, risk_upper = _clopper_pearson_interval(errors, len(covered), policy.alpha, one_sided=True)
    ranked = sorted(rows, key=lambda row: (row["risk_score"], row["example_id"]))
    target_count = max(1, math.ceil(policy.target_coverage * count))
    target_rows = ranked[:target_count]
    target_errors = sum(not row["correct"] for row in target_rows)
    target_risk = target_errors / target_count
    _, target_risk_upper = _clopper_pearson_interval(
        target_errors,
        target_count,
        policy.alpha,
        one_sided=True,
    )
    prefix_errors = 0
    prefix_risks: list[float] = []
    for index, row in enumerate(ranked, start=1):
        prefix_errors += int(not row["correct"])
        prefix_risks.append(prefix_errors / index)
    aurc = sum(prefix_risks) / count
    nil_precision_interval = _clopper_pearson_interval(true_positive, true_positive + false_positive, policy.alpha)
    nil_recall_interval = _clopper_pearson_interval(true_positive, true_positive + false_negative, policy.alpha)
    return {
        "metrics": {
            "top_label_accuracy": sum(row["correct"] for row in rows) / count,
            "multiclass_brier": sum(row["brier"] for row in rows) / count,
            "log_loss": sum(row["log_loss"] for row in rows) / count,
            "top_label_ece": ece,
            "nil_precision": nil_precision,
            "nil_recall": nil_recall,
            "coverage": coverage,
            "selective_risk": selective_risk,
            "selective_risk_upper_bound": risk_upper,
            "target_coverage_achieved": target_count / count,
            "target_selective_risk": target_risk,
            "target_selective_risk_upper_bound": target_risk_upper,
            "aurc": aurc,
        },
        "intervals": {
            "nil_precision": {"lower": nil_precision_interval[0], "upper": nil_precision_interval[1], "method": "CLOPPER_PEARSON_TWO_SIDED"},
            "nil_recall": {"lower": nil_recall_interval[0], "upper": nil_recall_interval[1], "method": "CLOPPER_PEARSON_TWO_SIDED"},
            "selective_risk": {"lower": None, "upper": risk_upper, "method": "CLOPPER_PEARSON_ONE_SIDED_UPPER"},
        },
        "ece_bins": bins,
        "counts": {
            "rows": count,
            "covered": len(covered),
            "errors": errors,
            "target_count": target_count,
            "target_errors": target_errors,
            "nil_tp": true_positive,
            "nil_fp": false_positive,
            "nil_fn": false_negative,
        },
    }


def _actual_interval_gate_checks(
    actual_bootstrap: Mapping[str, Any],
    policy: CalibrationEvaluationPolicy,
) -> dict[str, bool]:
    paired = actual_bootstrap.get("paired_deltas")
    checks: dict[str, bool] = {}
    for metric, bound in policy.paired_delta_ci_bounds.items():
        interval = paired.get(metric) if isinstance(paired, Mapping) else None
        direction = "lower" if metric == "top_label_accuracy" else "upper"
        value = interval.get(direction) if isinstance(interval, Mapping) else None
        finite = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
        if metric == "top_label_accuracy":
            passed = finite and float(value) >= bound
        else:
            passed = finite and float(value) <= bound
        checks[f"paired_{metric}_{direction}_bound"] = bool(
            isinstance(interval, Mapping)
            and interval.get("estimable") is True
            and passed
        )
    return checks


def _shadow_binding_matches(
    assignment: CalibrationSplitAssignment,
    shadow: CalibrationShadow,
    split_manifest: CalibrationSplitManifest,
    policy: CalibrationEvaluationPolicy,
) -> bool:
    labels = [item.label for item in shadow.event_probabilities]
    return bool(
        shadow.schema_version == CALIBRATION_SHADOW_SCHEMA
        and shadow.probability_status == CALIBRATED_BOUND_STATUS
        and shadow.generation_status == "COMPLETE"
        and shadow.candidate_set_recall_status == "READY_FOR_GOLD_EVALUATION"
        and shadow.candidate_set_fingerprint == assignment.candidate_set_fingerprint
        and shadow.post_id == assignment.post_id
        and shadow.example_id == assignment.example_id
        and shadow.split_manifest_sha256 == split_manifest.manifest_sha256
        and shadow.policy_sha256 == policy.policy_sha256
        and assignment.truth_label in labels
    )


def _rebuild_shadow_matches(
    assignment: CalibrationSplitAssignment,
    shadow: CalibrationShadow,
    base_shadow: SelectiveShadowDecision,
    score_vector: EventScoreVector,
    artifact: CalibrationArtifact,
    split_manifest: CalibrationSplitManifest,
    policy: CalibrationEvaluationPolicy,
) -> bool:
    rebuilt = build_calibration_shadow(
        base_shadow,
        score_vector,
        artifact,
        policy,
        split_manifest=split_manifest,
        assignment=assignment,
    )
    return bool(
        rebuilt.schema_version == CALIBRATION_SHADOW_SCHEMA
        and rebuilt.to_dict() == shadow.to_dict()
        and shadow.score_vector_sha256 == score_vector.score_vector_sha256
        and shadow.calibration_artifact_sha256 == artifact.artifact_sha256
        and shadow.generation_proof_fingerprint
        == score_vector.generation_proof_fingerprint
        and shadow.retrieval_state_fingerprint
        == score_vector.retrieval_state_fingerprint
        and shadow.publication_input_fingerprint
        == score_vector.publication_input_fingerprint
        and shadow.feature_fingerprint == score_vector.feature_fingerprint
    )


def evaluate_frozen_holdout(
    *,
    split_manifest: CalibrationSplitManifest,
    shadows: Mapping[str, CalibrationShadow],
    policy: CalibrationEvaluationPolicy,
    evidence_mode: str,
    base_shadows: Optional[Mapping[str, SelectiveShadowDecision]] = None,
    score_vectors: Optional[Mapping[str, EventScoreVector]] = None,
    calibration_artifact: Optional[CalibrationArtifact] = None,
    baseline_shadows: Optional[Mapping[str, CalibrationShadow]] = None,
    baseline_base_shadows: Optional[Mapping[str, SelectiveShadowDecision]] = None,
    baseline_score_vectors: Optional[Mapping[str, EventScoreVector]] = None,
    baseline_calibration_artifact: Optional[CalibrationArtifact] = None,
    actual_evidence_receipt: Optional[FrozenActualEvidenceReceipt] = None,
    prediction_artifact_sha256: Optional[str] = None,
    baseline_prediction_artifact_sha256: Optional[str] = None,
    run_spec_sha256: Optional[str] = None,
    producer_receipt_artifact_sha256: Optional[str] = None,
    actual_readback_manifest: Optional[Mapping[str, Any]] = None,
    actual_bootstrap_seed: int = 0,
    actual_bootstrap_replicates: int = 2000,
    actual_readback_root: Optional[str] = None,
) -> dict[str, Any]:
    if evidence_mode not in CALIBRATION_EVIDENCE_MODES:
        raise ValueError("unsupported calibration evidence_mode")
    frozen_all = [item for item in split_manifest.assignments if item.split == "FROZEN_HOLDOUT"]
    frozen = [item for item in frozen_all if item.truth_kind in {"CANDIDATE", "NIL"}]
    try:
        shadows = dict(shadows)
        base_shadows = None if base_shadows is None else dict(base_shadows)
        score_vectors = None if score_vectors is None else dict(score_vectors)
        baseline_shadows = (
            None if baseline_shadows is None else dict(baseline_shadows)
        )
        baseline_base_shadows = (
            None
            if baseline_base_shadows is None
            else dict(baseline_base_shadows)
        )
        baseline_score_vectors = (
            None
            if baseline_score_vectors is None
            else dict(baseline_score_vectors)
        )
    except (TypeError, ValueError) as error:
        return _early_evaluation(
            status="NOT_EVALUABLE_SOURCE_BINDING_INVALID",
            reason=f"source mapping snapshot failed: {error}",
            frozen_count=len(frozen),
        )
    if (
        evidence_mode == "FROZEN_ACTUAL"
        and policy.policy_scope != "FROZEN_ACTUAL_PRE_REGISTERED"
    ):
        return _early_evaluation(
            status="NO_GO_POLICY_SCOPE_MISMATCH",
            reason="FROZEN_ACTUAL requires a pre-registered actual policy",
            frozen_count=len(frozen_all),
        )
    if len(frozen) != len(frozen_all):
        return _early_evaluation(
            status="NOT_EVALUABLE_UNJUDGED_FROZEN_ROWS",
            reason="FROZEN_HOLDOUT contains UNJUDGED rows",
            frozen_count=len(frozen_all),
        )
    expected_ids = {item.example_id for item in frozen}
    if set(shadows) != expected_ids:
        return _early_evaluation(
            status="NOT_EVALUABLE_PREDICTION_COVERAGE",
            reason="frozen prediction example set mismatch",
            frozen_count=len(frozen),
        )
    if (
        base_shadows is None
        or score_vectors is None
        or calibration_artifact is None
        or set(base_shadows) != expected_ids
        or set(score_vectors) != expected_ids
    ):
        return _early_evaluation(
            status="NOT_EVALUABLE_SOURCE_BINDING_MISSING",
            reason="base shadows, score vectors, and one calibration artifact are required",
            frozen_count=len(frozen),
        )
    try:
        calibration_artifact.validate_against(split_manifest, policy)
        if (
            calibration_artifact.split_manifest_sha256 != split_manifest.manifest_sha256
            or calibration_artifact.calibration_split_fingerprint
            != split_manifest.split_fingerprints["CALIBRATION"]
            or calibration_artifact.frozen_holdout_fingerprint
            != split_manifest.split_fingerprints["FROZEN_HOLDOUT"]
            or calibration_artifact.policy_sha256 != policy.policy_sha256
        ):
            raise ValueError("after calibration artifact is not bound to the frozen manifest")
        if any(
            not _rebuild_shadow_matches(
                assignment,
                shadows[assignment.example_id],
                base_shadows[assignment.example_id],
                score_vectors[assignment.example_id],
                calibration_artifact,
                split_manifest,
                policy,
            )
            for assignment in frozen
        ):
            raise ValueError("after calibration shadow does not replay from bound sources")
    except (KeyError, TypeError, ValueError) as error:
        return _early_evaluation(
            status="NOT_EVALUABLE_SOURCE_BINDING_INVALID",
            reason=str(error),
            frozen_count=len(frozen),
        )
    retrieval_blocker_count = sum(
        "retrieval_failclose_requires_abstain" in shadow.reason_codes
        for shadow in shadows.values()
    )
    if retrieval_blocker_count:
        return _early_evaluation(
            status="NOT_EVALUABLE_RETRIEVAL_BLOCKED",
            reason=(
                f"{retrieval_blocker_count} frozen rows require retrieval fail-close; "
                "headline probability metrics remain null"
            ),
            frozen_count=len(frozen),
        )
    actual_bootstrap: Optional[dict[str, Any]] = None
    if evidence_mode == "FROZEN_ACTUAL":
        if actual_evidence_receipt is None:
            return _early_evaluation(
                status="NOT_ESTIMABLE_ACTUAL_EVIDENCE_MISSING",
                reason="FROZEN_ACTUAL requires an immutable evidence receipt",
                frozen_count=len(frozen),
            )
        try:
            actual_evidence_receipt.validate()
            prediction_sha = _require_sha256(
                prediction_artifact_sha256, "prediction_artifact_sha256"
            )
            baseline_prediction_sha = _require_sha256(
                baseline_prediction_artifact_sha256,
                "baseline_prediction_artifact_sha256",
            )
            run_spec_sha = _require_sha256(run_spec_sha256, "run_spec_sha256")
            producer_receipt_sha = _require_sha256(
                producer_receipt_artifact_sha256,
                "producer_receipt_artifact_sha256",
            )
            generation_proof_set_sha = _canonical_hash(
                sorted(
                    score.generation_proof_fingerprint
                    for score in score_vectors.values()
                )
            )
            if (
                actual_evidence_receipt.split_manifest_sha256
                != split_manifest.manifest_sha256
                or actual_evidence_receipt.source_label_ledger_sha256
                != split_manifest.source_label_ledger_sha256
                or actual_evidence_receipt.prediction_artifact_sha256
                != prediction_sha
                or actual_evidence_receipt.baseline_prediction_artifact_sha256
                != baseline_prediction_sha
                or actual_evidence_receipt.run_spec_sha256 != run_spec_sha
                or actual_evidence_receipt.producer_receipt_artifact_sha256
                != producer_receipt_sha
                or actual_evidence_receipt.calibrator_fit_receipt_sha256
                != calibration_artifact.calibrator_fit_receipt_sha256
                or actual_evidence_receipt.generation_proof_set_sha256
                != generation_proof_set_sha
                or actual_evidence_receipt.metric_protocol_sha256
                != policy.policy_sha256
            ):
                raise ValueError("FROZEN_ACTUAL evidence receipt binding mismatch")
        except (TypeError, ValueError) as error:
            return _early_evaluation(
                status="NO_GO_ACTUAL_EVIDENCE_RECEIPT_INVALID",
                reason=str(error),
                frozen_count=len(frozen),
            )
        if actual_readback_manifest is None:
            return _early_evaluation(status="NOT_ESTIMABLE_ACTUAL_READBACK_MISSING", reason="FROZEN_ACTUAL requires an independently validated readback manifest", frozen_count=len(frozen))
        if not actual_readback_root:
            return _early_evaluation(status="NOT_ESTIMABLE_ACTUAL_READBACK_ROOT_MISSING", reason="FROZEN_ACTUAL requires an explicit artifact root", frozen_count=len(frozen))
        try:
            validate_readback_manifest(actual_readback_manifest)
            artifact_rows = validate_actual_readback_artifacts(
                actual_readback_root,
                actual_readback_manifest,
            )
            if actual_readback_manifest.get("run_spec_sha256") != run_spec_sha:
                raise ValueError("actual readback RunSpec mismatch")
            if actual_readback_manifest.get("metric_protocol_sha256") != policy.policy_sha256:
                raise ValueError("actual readback metric protocol mismatch")
            if (
                actual_readback_manifest.get("bootstrap_seed") != actual_bootstrap_seed
                or actual_readback_manifest.get("bootstrap_replicates")
                != actual_bootstrap_replicates
            ):
                raise ValueError("actual readback evaluation plan mismatch")
            artifact_refs = actual_readback_manifest["artifacts"]
            if set(("expected_universe", "prediction", "baseline_prediction", "producer")) - set(artifact_refs):
                raise ValueError("actual readback artifact refs are incomplete")
            if (
                artifact_refs["prediction"]["sha256"] != prediction_sha
                or artifact_refs["baseline_prediction"]["sha256"] != baseline_prediction_sha
                or artifact_refs["producer"]["sha256"] != producer_receipt_sha
                or artifact_refs["expected_universe"]["sha256"]
                != actual_evidence_receipt.expected_universe_artifact_sha256
                or actual_readback_manifest["manifest_sha256"]
                != actual_evidence_receipt.readback_manifest_sha256
                or actual_readback_manifest["evaluation_plan_sha256"]
                != actual_evidence_receipt.evaluation_plan_sha256
            ):
                raise ValueError("actual readback artifact SHA binding mismatch")
            producer_rows = actual_readback_manifest["producer_coverage"]["per_row"]
            prediction_rows = actual_readback_manifest["prediction"]["per_row"]
            baseline_readback_rows = actual_readback_manifest["baseline_prediction"]["per_row"]
            stored_expected_rows = artifact_rows["expected_universe"]
            stored_after_rows = artifact_rows["prediction"]
            stored_baseline_rows = artifact_rows["baseline_prediction"]
            expected_order = [(item.example_id, item.post_id) for item in frozen]
            if [
                (row["example_id"], row["post_id"])
                for row in stored_expected_rows
            ] != expected_order:
                raise ValueError("actual expected universe does not exactly match FROZEN rows")
            if [(row["example_id"], row["post_id"]) for row in producer_rows] != expected_order:
                raise ValueError("actual producer coverage does not exactly match FROZEN rows")
            for assignment, row in zip(frozen, prediction_rows):
                shadow = shadows[assignment.example_id]
                if row["candidate_set_fingerprint"] != shadow.candidate_set_fingerprint or row["generation_proof_fingerprint"] != shadow.generation_proof_fingerprint:
                    raise ValueError("actual prediction readback binding mismatch")
            if len(stored_after_rows) != len(frozen) or len(stored_baseline_rows) != len(frozen):
                raise ValueError("stored prediction row coverage mismatch")
            for assignment, readback_row, baseline_readback_row, stored, baseline_stored in zip(
                frozen,
                prediction_rows,
                baseline_readback_rows,
                stored_after_rows,
                stored_baseline_rows,
            ):
                shadow = shadows[assignment.example_id]
                baseline_shadow = None if baseline_shadows is None else baseline_shadows.get(assignment.example_id)
                score = score_vectors[assignment.example_id]
                baseline_score = None if baseline_score_vectors is None else baseline_score_vectors.get(assignment.example_id)
                if baseline_shadow is None or baseline_score is None:
                    raise ValueError("stored baseline binding missing")
                for payload, bound_shadow, bound_score in ((stored, shadow, score), (baseline_stored, baseline_shadow, baseline_score)):
                    if (payload.get("example_id"), payload.get("post_id"), payload.get("group")) != (assignment.example_id, assignment.post_id, assignment.split_group_id):
                        raise ValueError("stored prediction identity/group mismatch")
                    if payload.get("shadow_fingerprint") != bound_shadow.shadow_fingerprint or payload.get("score_vector_sha256") != bound_score.score_vector_sha256:
                        raise ValueError("stored prediction shadow/score mismatch")
                    if payload.get("candidate_set_fingerprint") != bound_shadow.candidate_set_fingerprint or payload.get("generation_proof_fingerprint") != bound_shadow.generation_proof_fingerprint:
                        raise ValueError("stored prediction source binding mismatch")
                    expected_probabilities = {item.label: item.probability_mass for item in bound_shadow.event_probabilities}
                    if payload.get("probabilities") != expected_probabilities:
                        raise ValueError("stored prediction probability payload mismatch")
                if _canonical_hash(stored) != readback_row.get("payload_sha256"):
                    raise ValueError("stored after prediction payload digest mismatch")
                if _canonical_hash(baseline_stored) != baseline_readback_row.get("payload_sha256"):
                    raise ValueError("stored baseline prediction payload digest mismatch")
                if stored.get("source_digest_sha256") != readback_row.get("source_digest_sha256"):
                    raise ValueError("stored after prediction source digest mismatch")
                if baseline_stored.get("source_digest_sha256") != baseline_readback_row.get("source_digest_sha256"):
                    raise ValueError("stored baseline prediction source digest mismatch")
                if baseline_stored.get("source_digest_sha256") != stored.get("source_digest_sha256"):
                    raise ValueError("baseline/after source digest mismatch")
        except (KeyError, TypeError, ValueError) as error:
            return _early_evaluation(status="NOT_ESTIMABLE_ACTUAL_READBACK_INVALID", reason=str(error), frozen_count=len(frozen))
    candidate_rows = [item for item in frozen if item.truth_kind == "CANDIDATE"]
    candidate_hits = 0
    binding_failure = False
    for assignment in frozen:
        shadow = shadows[assignment.example_id]
        labels = [item.label for item in shadow.event_probabilities]
        if not _shadow_binding_matches(assignment, shadow, split_manifest, policy):
            binding_failure = True
        if assignment.truth_kind == "CANDIDATE" and assignment.truth_label in labels:
            candidate_hits += 1
        if assignment.truth_label not in labels:
            binding_failure = True
    recall_denominator = len(candidate_rows)
    recall_value = candidate_hits / recall_denominator if recall_denominator else None
    recall_lower, _ = _clopper_pearson_interval(candidate_hits, recall_denominator, policy.alpha, one_sided=True)
    recall = {
        "value": recall_value,
        "numerator": candidate_hits,
        "denominator": recall_denominator,
        "lower_bound": recall_lower,
        "interval_method": "CLOPPER_PEARSON_ONE_SIDED_LOWER",
    }
    if binding_failure or candidate_hits != recall_denominator:
        return _early_evaluation(
            status="NOT_EVALUABLE_CANDIDATE_SET_INCOMPLETE",
            reason="candidate truth is missing or a frozen binding is invalid",
            frozen_count=len(frozen),
            candidate_recall=recall,
        )
    truth_counts = {
        kind: sum(item.truth_kind == kind for item in frozen)
        for kind in ("CANDIDATE", "NIL")
    }
    if len(frozen) < policy.min_frozen_rows or any(
        count < policy.min_per_truth_class for count in truth_counts.values()
    ):
        return _early_evaluation(
            status="NOT_ESTIMABLE_SMALL_SAMPLE",
            reason="frozen sample or truth stratum is below the pre-registered minimum",
            frozen_count=len(frozen),
            candidate_recall=recall,
        )
    if recall_lower is None or recall_lower < policy.min_candidate_recall_lower_bound:
        return _early_evaluation(
            status="NO_GO_CANDIDATE_RECALL_LOWER_BOUND",
            reason="candidate-set recall lower bound is below the pre-registered threshold",
            frozen_count=len(frozen),
            candidate_recall=recall,
        )
    try:
        bundle = _metric_bundle(frozen, shadows, policy)
    except ArithmeticError as error:
        return _early_evaluation(
            status="LOGLOSS_INVALID",
            reason=str(error),
            frozen_count=len(frozen),
            candidate_recall=recall,
        )
    occupied = [item for item in bundle["ece_bins"] if item["count"]]
    if any(item["count"] < policy.min_occupied_bin_rows for item in occupied):
        return _early_evaluation(
            status="NOT_ESTIMABLE_SMALL_BIN",
            reason="occupied ECE bin is below the pre-registered minimum",
            frozen_count=len(frozen),
            candidate_recall=recall,
        )
    baseline_bundle = None
    if baseline_shadows is not None:
        if (
            baseline_base_shadows is None
            or baseline_score_vectors is None
            or baseline_calibration_artifact is None
            or set(baseline_shadows) != expected_ids
            or set(baseline_base_shadows) != expected_ids
            or set(baseline_score_vectors) != expected_ids
        ):
            return _early_evaluation(
                status="NO_GO_BASELINE_ROW_MISMATCH",
                reason="baseline source objects do not use the same frozen examples",
                frozen_count=len(frozen),
                candidate_recall=recall,
            )
        if (
            baseline_calibration_artifact.artifact_sha256
            == calibration_artifact.artifact_sha256
            or baseline_calibration_artifact.scorer_fingerprint
            == calibration_artifact.scorer_fingerprint
        ):
            return _early_evaluation(
                status="NO_GO_BASELINE_IDENTITY_COLLISION",
                reason="baseline must bind a distinct pre-registered scorer and calibration artifact",
                frozen_count=len(frozen),
                candidate_recall=recall,
            )
        try:
            baseline_calibration_artifact.validate_against(split_manifest, policy)
            if (
                baseline_calibration_artifact.split_manifest_sha256
                != split_manifest.manifest_sha256
                or baseline_calibration_artifact.calibration_split_fingerprint
                != split_manifest.split_fingerprints["CALIBRATION"]
                or baseline_calibration_artifact.frozen_holdout_fingerprint
                != split_manifest.split_fingerprints["FROZEN_HOLDOUT"]
                or baseline_calibration_artifact.policy_sha256 != policy.policy_sha256
                or (
                    evidence_mode == "FROZEN_ACTUAL"
                    and actual_evidence_receipt is not None
                    and actual_evidence_receipt.baseline_calibrator_fit_receipt_sha256
                    != baseline_calibration_artifact.calibrator_fit_receipt_sha256
                )
                or any(
                    not _rebuild_shadow_matches(
                        assignment,
                        baseline_shadows[assignment.example_id],
                        baseline_base_shadows[assignment.example_id],
                        baseline_score_vectors[assignment.example_id],
                        baseline_calibration_artifact,
                        split_manifest,
                        policy,
                    )
                    for assignment in frozen
                )
            ):
                raise ValueError(
                    "baseline rows are not exactly bound to one frozen artifact"
                )
            baseline_bundle = _metric_bundle(frozen, baseline_shadows, policy)
        except (ArithmeticError, KeyError, TypeError, ValueError) as error:
            return _early_evaluation(
                status="NO_GO_BASELINE_INVALID_BINDING",
                reason=str(error),
                frozen_count=len(frozen),
                candidate_recall=recall,
            )
    metrics = bundle["metrics"]
    if evidence_mode == "FROZEN_ACTUAL":
        if baseline_bundle is None or baseline_shadows is None:
            return _early_evaluation(status="NOT_ESTIMABLE_ACTUAL_BASELINE_MISSING", reason="same-row baseline is required for actual confidence intervals", frozen_count=len(frozen), candidate_recall=recall)
        def _bootstrap_rows(source: Mapping[str, CalibrationShadow]) -> list[dict[str, Any]]:
            output: list[dict[str, Any]] = []
            for assignment in frozen:
                shadow = source[assignment.example_id]
                probabilities = {item.label: float(item.probability) for item in shadow.event_probabilities}
                truth = str(assignment.truth_label)
                selected = str(shadow.selected_label)
                output.append({
                    "example_id": assignment.example_id,
                    "group": assignment.split_group_id,
                    "correct": selected == truth,
                    "abstain": shadow.action == SHADOW_ACTION_ABSTAIN,
                    "confidence": probabilities[selected],
                    "risk_score": shadow.selected_error_probability_mass / PROBABILITY_SCALE,
                    "brier": sum((probability - (1.0 if label == truth else 0.0)) ** 2 for label, probability in probabilities.items()),
                    "log_loss": -math.log(probabilities[truth]),
                })
            return output
        try:
            actual_bootstrap = cluster_bootstrap(
                _bootstrap_rows(shadows),
                baseline_rows=_bootstrap_rows(baseline_shadows),
                seed=actual_bootstrap_seed,
                replicates=actual_bootstrap_replicates,
                alpha=policy.alpha,
                min_group_count=2,
                ece_bin_edges=policy.fixed_bin_edges,
                top_label_accuracy_denominator=(
                    policy.top_label_accuracy_denominator
                ),
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as error:
            return _early_evaluation(status="NOT_ESTIMABLE_ACTUAL_INTERVAL_INVALID", reason=str(error), frozen_count=len(frozen), candidate_recall=recall)
        if not actual_bootstrap.get("estimable"):
            return _early_evaluation(status="NOT_ESTIMABLE_ACTUAL_INTERVALS", reason=str(actual_bootstrap.get("reason") or "cluster bootstrap intervals are incomplete"), frozen_count=len(frozen), candidate_recall=recall)
    retrieval_violations = sum(
        "retrieval_failclose_requires_abstain" in shadow.reason_codes
        and shadow.action != SHADOW_ACTION_ABSTAIN
        for shadow in shadows.values()
    )
    metric_gates_passed = False
    point_metric_checks_passed = False
    point_metric_checks: dict[str, bool] = {}
    interval_metric_checks_passed = False
    interval_metric_checks: dict[str, bool] = {}
    conversion_allowed = False
    if evidence_mode == "SYNTHETIC_CONTRACT_ONLY":
        status = "GO_SYNTHETIC_METRIC_CONTRACT_ONLY"
        conversion_reason = "SYNTHETIC_EVIDENCE_NEVER_DEPLOYMENT"
    elif baseline_bundle is None:
        status = "NO_GO_BASELINE_MISSING"
        conversion_reason = "same-row baseline comparison is required"
    else:
        baseline_metrics = baseline_bundle["metrics"]
        nil_precision_lower = bundle["intervals"]["nil_precision"]["lower"]
        nil_recall_lower = bundle["intervals"]["nil_recall"]["lower"]
        checks = {
            "target_coverage_attained": metrics["coverage"] >= policy.target_coverage,
            "selective_risk_upper": metrics["selective_risk_upper_bound"] is not None
            and metrics["selective_risk_upper_bound"]
            <= policy.max_selective_risk_upper_bound,
            "baseline_noninferiority": metrics["target_selective_risk"] is not None
            and baseline_metrics["target_selective_risk"] is not None
            and metrics["target_selective_risk"]
            <= baseline_metrics["target_selective_risk"]
            + policy.baseline_noninferiority_margin,
            "retrieval_failclose": retrieval_violations == 0,
            "nil_prediction_count": bundle["counts"]["nil_tp"]
            + bundle["counts"]["nil_fp"]
            >= policy.min_nil_prediction_count,
            "nil_precision_lower_bound": nil_precision_lower is not None
            and nil_precision_lower >= policy.min_nil_precision_lower_bound,
            "nil_recall_lower_bound": nil_recall_lower is not None
            and nil_recall_lower >= policy.min_nil_recall_lower_bound,
        }
        point_metric_checks = checks
        point_metric_checks_passed = all(checks.values())
        if evidence_mode == "FROZEN_ACTUAL" and actual_bootstrap is not None:
            interval_metric_checks = _actual_interval_gate_checks(actual_bootstrap, policy)
            interval_metric_checks_passed = all(interval_metric_checks.values())
            if point_metric_checks_passed and interval_metric_checks_passed:
                status = "GO_FROZEN_ACTUAL_SHADOW_ONLY"
                metric_gates_passed = True
                conversion_reason = "ACTUAL_READBACK_AND_CLUSTER_INTERVAL_GATES_VALID_SHADOW_ONLY"
            elif point_metric_checks_passed:
                status = "NO_GO_INTERVAL_METRIC_GATES"
                conversion_reason = "paired selective-risk confidence bound failed noninferiority"
            else:
                status = "NO_GO_METRIC_GATES"
                conversion_reason = "one or more pre-registered point metric gates failed"
        elif point_metric_checks_passed:
            status = "NO_GO_INTERVAL_PROTOCOL_INCOMPLETE"
            conversion_reason = (
                "ECE/Brier/log-loss/AURC and paired baseline confidence intervals "
                "are not yet implemented; publication conversion remains forbidden"
            )
        else:
            status = "NO_GO_METRIC_GATES"
            conversion_reason = "one or more pre-registered metric gates failed"
    correct_count = sum(shadows[item.example_id].selected_label == item.truth_label for item in frozen)
    accuracy_interval = actual_bootstrap["intervals"]["top_label_accuracy"] if actual_bootstrap is not None else None
    return {
        "schema_version": "candidate_set_calibration_evaluation_v1",
        "status": status,
        "evidence_mode": evidence_mode,
        "frozen_count": len(frozen),
        "truth_counts": truth_counts,
        "candidate_set_recall": recall,
        "metrics": metrics,
        "intervals": bundle["intervals"],
        "cluster_bootstrap": actual_bootstrap,
        "top_label_accuracy_receipt": ({
            "numerator": correct_count,
            "denominator": len(frozen),
            "value": correct_count / len(frozen),
            "percent": 100.0 * correct_count / len(frozen),
            "confidence_level": 1.0 - policy.alpha,
            "cluster_ci": accuracy_interval,
        } if actual_bootstrap is not None else None),
        "ece_bins": bundle["ece_bins"],
        "counts": {**bundle["counts"], "retrieval_failclose_violations": retrieval_violations},
        "baseline_metrics": baseline_bundle["metrics"] if baseline_bundle is not None else None,
        "metric_gates_passed": metric_gates_passed,
        "point_metric_checks": point_metric_checks,
        "point_metric_checks_passed": point_metric_checks_passed,
        "interval_metric_checks": interval_metric_checks,
        "interval_metric_checks_passed": interval_metric_checks_passed,
        "conversion_allowed": conversion_allowed,
        "conversion_reason": conversion_reason,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
