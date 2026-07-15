"""Fail-closed selective-compute routing contracts.

P4 chooses only a *compute lane*.  It never changes a publication decision,
candidate set, title, URL, or promotion-gate output.  Unknown or unbound
evidence always selects the existing full-expert lane.  A cheap lane can be
observed only when every pre-registered safety prerequisite is positively
bound.  All receipts are immutable, self-fingerprinted sidecars.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple


DECISION_COST_TRACE_SCHEMA = "decision_cost_trace_v1"
ROUTING_POLICY_SCHEMA = "selective_compute_policy_v1"
ROUTING_OBSERVATION_SCHEMA = "selective_compute_observation_v1"
ROUTING_RECEIPT_SCHEMA = "selective_compute_router_shadow_v1"
ROUTING_EVALUATION_SCHEMA = "selective_compute_evaluation_v1"

SHADOW_OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
LANE_FULL_EXPERT = "FULL_EXPERT_REQUIRED"
LANE_CHEAP_RULE = "CHEAP_RULE_ELIGIBLE"

ACTION_NONE = "NONE"
ACTION_RESOLVE = "RESOLVE"
ACTION_ASSERT_NIL = "ASSERT_NIL"
NIL_LABEL = "__NIL__"

EVIDENCE_SCOPE_SAVED = "SAVED_GOLDEN_READINESS"
EVIDENCE_SCOPE_SYNTHETIC = "SYNTHETIC_CONTRACT_ONLY"
EVIDENCE_SCOPE_FROZEN_ACTUAL = "FROZEN_ACTUAL"

COST_STATUS_NOT_AVAILABLE = "NOT_AVAILABLE"
COST_STATUS_PARTIAL_LOG = "PARTIAL_SIDECAR_LOG"
COST_STATUS_PARTIAL_RUNTIME = "PARTIAL_AGGREGATE_NO_CALL_EVENTS"
COST_STATUS_STRUCTURED = "STRUCTURED_CALL_EVENTS_COMPLETE"
COST_STATUS_SYNTHETIC = "SYNTHETIC_COMPLETE"

HARD_RISK_CODES: Tuple[str, ...] = tuple(
    sorted(
        {
            "BUDGET_SCOPE_INVALID",
            "ACTUAL_SOURCE_READBACK_NOT_IMPLEMENTED",
            "CALIBRATION_ACTUAL_NOT_BOUND",
            "CANDIDATE_GENERATION_TRUNCATED",
            "CANDIDATE_GENERATION_UNKNOWN",
            "CHEAP_TERMINAL_NOT_VERIFIED",
            "MULTI_WORK_OR_IDENTITY_CONFLICT",
            "PRODUCER_PROOF_NOT_COMPLETE",
            "PUBLICATION_HOLD_OR_QUARANTINE",
            "SCOPE_UNKNOWN_OR_NOT_CURRENT_WORK",
            "SEARCH_DEGRADED_OR_BLOCKED",
            "SEARCH_REQUIRED_OR_UNKNOWN",
            "SOURCE_BINDING_INVALID",
            "UNJUDGED_OR_INVALID_VERDICT",
            "VLM_OCR_REQUIRED_NOT_COMPLETE",
            "VLM_OCR_TITLE_CONFLICT",
        }
    )
)

REQUIRED_BINDING_NAMES: Tuple[str, ...] = tuple(
    sorted(
        {
            "budget_scope",
            "candidate_generation_metadata",
            "candidate_producer_plan_set",
            "candidate_producer_receipt_set",
            "candidate_set",
            "comments",
            "image_evidence_catalog",
            "image_url_inventory",
            "judge_packet",
            "judge_verdict",
            "post_content_blocks",
            "promotion_gate_evidence",
            "promotion_gate_state",
            "retrieval_state",
            "scope_state",
            "search_health",
            "source_input",
            "vlm_ocr_execution",
        }
    )
)

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


def canonical_hash(value: Any) -> str:
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


def _optional_nonnegative_int(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    return _strict_nonnegative_int(value, field_name)


def normalize_optional_nonnegative_count(value: Any) -> Optional[int]:
    """Preserve missing/invalid counters as null instead of laundering them to zero."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text and text.isascii() and text.isdigit():
            return int(text)
    return None


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be bool")
    return value


def _sorted_unique(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(sorted({_require_text(value, "sequence value") for value in values}))


def _require_choice(value: Any, field_name: str, choices: Sequence[str]) -> str:
    text = _require_text(value, field_name)
    if text not in choices:
        raise ValueError(f"unsupported {field_name}: {text}")
    return text


def _require_iso_timestamp(value: Any, field_name: str) -> str:
    text = _require_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone")
    return text


def _require_exact_keys(value: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    actual = set(value)
    expected_set = set(expected)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        extra = sorted(actual - expected_set)
        raise ValueError(f"{label} shape mismatch: missing={missing}, extra={extra}")


@dataclass(frozen=True)
class BindingDigest:
    name: str
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_text(self.name, "binding name"))
        object.__setattr__(self, "sha256", _require_sha256(self.sha256, self.name))

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "sha256": self.sha256}


def binding_digest_from_dict(value: Any) -> BindingDigest:
    if not isinstance(value, Mapping):
        raise ValueError("binding digest must be an object")
    _require_exact_keys(value, {"name", "sha256"}, "binding digest")
    return BindingDigest(name=value["name"], sha256=value["sha256"])


@dataclass(frozen=True)
class DecisionCostTrace:
    publication_scope_id: str
    run_id: str
    input_index: int
    post_id: str
    model_tier: str
    processing_started_at: str
    processing_finished_at: str
    wall_ms: int
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    expert_calls: Optional[int]
    search_calls: Optional[int]
    retry_count: Optional[int]
    vlm_chunks: Optional[int]
    measurement_status: str
    action_applied: bool
    operational_effect: str
    trace_sha256: str
    schema_version: str = DECISION_COST_TRACE_SCHEMA

    def __post_init__(self) -> None:
        for field_name in ("publication_scope_id", "run_id", "post_id", "model_tier"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        _strict_nonnegative_int(self.input_index, "input_index")
        started = _require_iso_timestamp(self.processing_started_at, "processing_started_at")
        finished = _require_iso_timestamp(self.processing_finished_at, "processing_finished_at")
        if datetime.fromisoformat(finished) < datetime.fromisoformat(started):
            raise ValueError("processing_finished_at precedes processing_started_at")
        _strict_nonnegative_int(self.wall_ms, "wall_ms")
        for field_name in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "search_calls",
            "retry_count",
            "vlm_chunks",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_nonnegative_int(getattr(self, field_name), field_name),
            )
        token_values = (self.prompt_tokens, self.completion_tokens, self.total_tokens)
        if any(value is None for value in token_values) and any(
            value is not None for value in token_values
        ):
            raise ValueError("token aggregate must be all available or all null")
        if all(value is not None for value in token_values) and self.total_tokens != (
            self.prompt_tokens + self.completion_tokens
        ):
            raise ValueError("total_tokens must equal prompt_tokens + completion_tokens")
        object.__setattr__(
            self,
            "measurement_status",
            _require_choice(
                self.measurement_status,
                "measurement_status",
                (COST_STATUS_PARTIAL_RUNTIME, COST_STATUS_STRUCTURED),
            ),
        )
        if self.measurement_status == COST_STATUS_PARTIAL_RUNTIME:
            if self.expert_calls is not None:
                raise ValueError("partial aggregate trace must not claim expert call completeness")
        else:
            _strict_nonnegative_int(self.expert_calls, "expert_calls")
            if any(
                value is None
                for value in (
                    self.prompt_tokens,
                    self.completion_tokens,
                    self.total_tokens,
                    self.search_calls,
                    self.retry_count,
                    self.vlm_chunks,
                )
            ):
                raise ValueError("structured call-event trace requires all numeric fields")
        if _strict_bool(self.action_applied, "action_applied"):
            raise ValueError("decision cost trace must never apply a decision")
        if self.operational_effect != SHADOW_OPERATIONAL_EFFECT:
            raise ValueError("decision cost trace must be shadow-only")
        _require_sha256(self.trace_sha256, "trace_sha256")
        if self.trace_sha256 != canonical_hash(self.payload_without_trace_sha256()):
            raise ValueError("decision cost trace fingerprint mismatch")

    @classmethod
    def create(
        cls,
        *,
        publication_scope_id: Any,
        run_id: Any,
        input_index: int,
        post_id: Any,
        model_tier: Any,
        processing_started_at: Any,
        processing_finished_at: Any,
        wall_ms: int,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: Optional[int],
        expert_calls: Optional[int],
        search_calls: Optional[int],
        retry_count: Optional[int],
        vlm_chunks: Optional[int],
        measurement_status: str = COST_STATUS_PARTIAL_RUNTIME,
    ) -> "DecisionCostTrace":
        payload = {
            "schema_version": DECISION_COST_TRACE_SCHEMA,
            "publication_scope_id": str(publication_scope_id),
            "run_id": str(run_id),
            "input_index": input_index,
            "post_id": str(post_id),
            "model_tier": str(model_tier),
            "processing_started_at": processing_started_at,
            "processing_finished_at": processing_finished_at,
            "wall_ms": wall_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "expert_calls": expert_calls,
            "search_calls": search_calls,
            "retry_count": retry_count,
            "vlm_chunks": vlm_chunks,
            "measurement_status": measurement_status,
            "action_applied": False,
            "operational_effect": SHADOW_OPERATIONAL_EFFECT,
        }
        return cls(**payload, trace_sha256=canonical_hash(payload))

    def payload_without_trace_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "publication_scope_id": self.publication_scope_id,
            "run_id": self.run_id,
            "input_index": self.input_index,
            "post_id": self.post_id,
            "model_tier": self.model_tier,
            "processing_started_at": self.processing_started_at,
            "processing_finished_at": self.processing_finished_at,
            "wall_ms": self.wall_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "expert_calls": self.expert_calls,
            "search_calls": self.search_calls,
            "retry_count": self.retry_count,
            "vlm_chunks": self.vlm_chunks,
            "measurement_status": self.measurement_status,
            "action_applied": self.action_applied,
            "operational_effect": self.operational_effect,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_trace_sha256(), "trace_sha256": self.trace_sha256}


def decision_cost_trace_from_dict(value: Any) -> DecisionCostTrace:
    if not isinstance(value, Mapping):
        raise ValueError("decision cost trace must be an object")
    expected = {
        "schema_version",
        "publication_scope_id",
        "run_id",
        "input_index",
        "post_id",
        "model_tier",
        "processing_started_at",
        "processing_finished_at",
        "wall_ms",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "expert_calls",
        "search_calls",
        "retry_count",
        "vlm_chunks",
        "measurement_status",
        "action_applied",
        "operational_effect",
        "trace_sha256",
    }
    _require_exact_keys(value, expected, "decision cost trace")
    if value["schema_version"] != DECISION_COST_TRACE_SCHEMA:
        raise ValueError("unsupported decision cost trace schema")
    return DecisionCostTrace(**dict(value))


@dataclass(frozen=True)
class SelectiveComputePolicy:
    evidence_scope: str
    policy_origin: str
    router_model_id: str
    cheap_lane_expert_calls: int
    unknown_is_hard_risk: bool
    hard_risk_codes: Tuple[str, ...]
    action_applied: bool
    operational_effect: str
    policy_sha256: str
    schema_version: str = ROUTING_POLICY_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_scope",
            _require_choice(
                self.evidence_scope,
                "evidence_scope",
                (
                    EVIDENCE_SCOPE_SAVED,
                    EVIDENCE_SCOPE_SYNTHETIC,
                    EVIDENCE_SCOPE_FROZEN_ACTUAL,
                ),
            ),
        )
        for field_name in ("policy_origin", "router_model_id"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        if _strict_nonnegative_int(self.cheap_lane_expert_calls, "cheap_lane_expert_calls") != 0:
            raise ValueError("v1 cheap rule lane must be deterministic and use zero expert calls")
        if _strict_bool(self.unknown_is_hard_risk, "unknown_is_hard_risk") is not True:
            raise ValueError("unknown evidence must be hard risk")
        object.__setattr__(self, "hard_risk_codes", _sorted_unique(self.hard_risk_codes))
        if self.hard_risk_codes != HARD_RISK_CODES:
            raise ValueError("policy hard-risk union mismatch")
        if _strict_bool(self.action_applied, "action_applied"):
            raise ValueError("routing policy must remain shadow-only")
        if self.operational_effect != SHADOW_OPERATIONAL_EFFECT:
            raise ValueError("routing policy operational effect mismatch")
        if self.schema_version != ROUTING_POLICY_SCHEMA:
            raise ValueError("unsupported routing policy schema")
        _require_sha256(self.policy_sha256, "policy_sha256")
        if self.policy_sha256 != canonical_hash(self.payload_without_policy_sha256()):
            raise ValueError("routing policy fingerprint mismatch")

    @classmethod
    def create(cls, evidence_scope: str) -> "SelectiveComputePolicy":
        payload = {
            "schema_version": ROUTING_POLICY_SCHEMA,
            "evidence_scope": evidence_scope,
            "policy_origin": "PRE_REGISTERED_DEV_FAIL_CLOSED",
            "router_model_id": "DETERMINISTIC_RULES_V1_NO_LLM",
            "cheap_lane_expert_calls": 0,
            "unknown_is_hard_risk": True,
            "hard_risk_codes": list(HARD_RISK_CODES),
            "action_applied": False,
            "operational_effect": SHADOW_OPERATIONAL_EFFECT,
        }
        return cls(
            evidence_scope=payload["evidence_scope"],
            policy_origin=payload["policy_origin"],
            router_model_id=payload["router_model_id"],
            cheap_lane_expert_calls=payload["cheap_lane_expert_calls"],
            unknown_is_hard_risk=payload["unknown_is_hard_risk"],
            hard_risk_codes=tuple(payload["hard_risk_codes"]),
            action_applied=payload["action_applied"],
            operational_effect=payload["operational_effect"],
            policy_sha256=canonical_hash(payload),
        )

    def payload_without_policy_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "policy_origin": self.policy_origin,
            "router_model_id": self.router_model_id,
            "cheap_lane_expert_calls": self.cheap_lane_expert_calls,
            "unknown_is_hard_risk": self.unknown_is_hard_risk,
            "hard_risk_codes": list(self.hard_risk_codes),
            "action_applied": self.action_applied,
            "operational_effect": self.operational_effect,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_policy_sha256(), "policy_sha256": self.policy_sha256}


def selective_compute_policy_from_dict(value: Any) -> SelectiveComputePolicy:
    if not isinstance(value, Mapping):
        raise ValueError("routing policy must be an object")
    expected = {
        "schema_version",
        "evidence_scope",
        "policy_origin",
        "router_model_id",
        "cheap_lane_expert_calls",
        "unknown_is_hard_risk",
        "hard_risk_codes",
        "action_applied",
        "operational_effect",
        "policy_sha256",
    }
    _require_exact_keys(value, expected, "routing policy")
    return SelectiveComputePolicy(
        evidence_scope=value["evidence_scope"],
        policy_origin=value["policy_origin"],
        router_model_id=value["router_model_id"],
        cheap_lane_expert_calls=value["cheap_lane_expert_calls"],
        unknown_is_hard_risk=value["unknown_is_hard_risk"],
        hard_risk_codes=tuple(value["hard_risk_codes"]),
        action_applied=value["action_applied"],
        operational_effect=value["operational_effect"],
        policy_sha256=value["policy_sha256"],
        schema_version=value["schema_version"],
    )


@dataclass(frozen=True)
class SelectiveComputeObservation:
    evidence_scope: str
    publication_scope_id: str
    attempt_run_id: str
    input_index: int
    post_id: str
    binding_digests: Tuple[BindingDigest, ...]
    publication_input_fingerprint: str
    baseline_decision_fingerprint: str
    baseline_publication_before_fingerprint: str
    baseline_publication_after_fingerprint: str
    candidate_set_before_fingerprint: str
    candidate_set_after_fingerprint: str
    source_binding_status: str
    search_requirement_status: str
    search_health_status: str
    producer_proof_status: str
    candidate_generation_status: str
    candidate_conflict_status: str
    vlm_ocr_requirement_status: str
    vlm_ocr_status: str
    publication_status: str
    judge_coverage_status: str
    scope_status: str
    calibration_status: str
    budget_binding_status: str
    cheap_terminal_status: str
    proposed_terminal_action: str
    proposed_selected_label: Optional[str]
    cost_evidence_status: str
    cost_evidence_digest: str
    baseline_expert_calls: Optional[int]
    baseline_total_tokens: Optional[int]
    baseline_wall_ms: Optional[int]
    observation_fingerprint: str
    schema_version: str = ROUTING_OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_scope",
            _require_choice(
                self.evidence_scope,
                "evidence_scope",
                (
                    EVIDENCE_SCOPE_SAVED,
                    EVIDENCE_SCOPE_SYNTHETIC,
                    EVIDENCE_SCOPE_FROZEN_ACTUAL,
                ),
            ),
        )
        for field_name in ("publication_scope_id", "attempt_run_id", "post_id"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        _strict_nonnegative_int(self.input_index, "input_index")
        bindings = tuple(self.binding_digests)
        if tuple(item.name for item in bindings) != REQUIRED_BINDING_NAMES:
            raise ValueError("binding digest names must exactly match the frozen source union")
        object.__setattr__(self, "binding_digests", bindings)
        for field_name in (
            "publication_input_fingerprint",
            "baseline_decision_fingerprint",
            "baseline_publication_before_fingerprint",
            "baseline_publication_after_fingerprint",
            "candidate_set_before_fingerprint",
            "candidate_set_after_fingerprint",
            "cost_evidence_digest",
            "observation_fingerprint",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        if self.baseline_publication_before_fingerprint != self.baseline_publication_after_fingerprint:
            raise ValueError("router observation must not change the public decision fingerprint")
        if self.candidate_set_before_fingerprint != self.candidate_set_after_fingerprint:
            raise ValueError("router observation must not change the candidate-set fingerprint")
        choices = {
            "source_binding_status": ("VALID", "INVALID", "UNKNOWN"),
            "search_requirement_status": ("REQUIRED", "NOT_REQUIRED", "UNKNOWN"),
            "search_health_status": ("HEALTHY", "DEGRADED", "BLOCKED", "NOT_APPLICABLE", "UNKNOWN"),
            "producer_proof_status": ("COMPLETE", "INCOMPLETE", "UNKNOWN"),
            "candidate_generation_status": ("COMPLETE", "TRUNCATED", "UNKNOWN"),
            "candidate_conflict_status": ("NONE", "MULTI_WORK", "IDENTITY_CONFLICT", "UNKNOWN"),
            "vlm_ocr_requirement_status": ("REQUIRED", "NOT_REQUIRED", "UNKNOWN"),
            "vlm_ocr_status": ("COMPLETE", "INCOMPLETE", "CONFLICT", "NOT_APPLICABLE", "UNKNOWN"),
            "publication_status": ("CLEAN", "HOLD", "ERROR_HOLD", "QUARANTINE", "UNKNOWN"),
            "judge_coverage_status": ("COMPLETE", "UNJUDGED", "INVALID", "UNKNOWN"),
            "scope_status": ("CURRENT_WORK", "NOT_CURRENT_WORK", "UNKNOWN"),
            "calibration_status": ("FROZEN_ACTUAL_BOUND", "SYNTHETIC_BOUND", "NOT_AVAILABLE", "UNKNOWN"),
            "budget_binding_status": ("VALID", "INVALID", "UNKNOWN"),
            "cheap_terminal_status": (
                "VERIFIED_DETERMINISTIC_NIL",
                "VERIFIED_DETERMINISTIC_RESOLVE",
                "NOT_VERIFIED",
                "UNKNOWN",
            ),
            "proposed_terminal_action": (ACTION_NONE, ACTION_RESOLVE, ACTION_ASSERT_NIL),
            "cost_evidence_status": (
                COST_STATUS_NOT_AVAILABLE,
                COST_STATUS_PARTIAL_LOG,
                COST_STATUS_PARTIAL_RUNTIME,
                COST_STATUS_STRUCTURED,
                COST_STATUS_SYNTHETIC,
            ),
        }
        for field_name, allowed in choices.items():
            object.__setattr__(
                self,
                field_name,
                _require_choice(getattr(self, field_name), field_name, allowed),
            )
        label = None if self.proposed_selected_label is None else _require_text(
            self.proposed_selected_label, "proposed_selected_label"
        )
        object.__setattr__(self, "proposed_selected_label", label)
        if self.cheap_terminal_status == "VERIFIED_DETERMINISTIC_NIL":
            if self.proposed_terminal_action != ACTION_ASSERT_NIL or label != NIL_LABEL:
                raise ValueError("verified NIL terminal requires ASSERT_NIL and __NIL__")
        elif self.cheap_terminal_status == "VERIFIED_DETERMINISTIC_RESOLVE":
            if self.proposed_terminal_action != ACTION_RESOLVE or label in (None, NIL_LABEL):
                raise ValueError("verified resolve terminal requires a non-NIL label")
        elif self.proposed_terminal_action != ACTION_NONE or label is not None:
            raise ValueError("unverified terminal must not propose a truth action")
        for field_name in (
            "baseline_expert_calls",
            "baseline_total_tokens",
            "baseline_wall_ms",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_nonnegative_int(getattr(self, field_name), field_name),
            )
        if self.cost_evidence_status == COST_STATUS_NOT_AVAILABLE and any(
            value is not None
            for value in (
                self.baseline_expert_calls,
                self.baseline_total_tokens,
                self.baseline_wall_ms,
            )
        ):
            raise ValueError("unavailable cost evidence must not expose numeric values")
        if self.evidence_scope != EVIDENCE_SCOPE_SYNTHETIC and self.cost_evidence_status == COST_STATUS_SYNTHETIC:
            raise ValueError("synthetic cost evidence cannot be promoted into an actual scope")
        if self.evidence_scope == EVIDENCE_SCOPE_SYNTHETIC and self.cost_evidence_status in {
            COST_STATUS_PARTIAL_LOG,
            COST_STATUS_PARTIAL_RUNTIME,
            COST_STATUS_STRUCTURED,
        }:
            raise ValueError("synthetic scope cannot consume actual runtime cost evidence")
        if self.evidence_scope != EVIDENCE_SCOPE_SYNTHETIC and self.calibration_status == "SYNTHETIC_BOUND":
            raise ValueError("synthetic calibration cannot be promoted into an actual scope")
        if self.evidence_scope == EVIDENCE_SCOPE_SYNTHETIC and self.calibration_status == "FROZEN_ACTUAL_BOUND":
            raise ValueError("synthetic scope cannot claim frozen-actual calibration")
        if self.cost_evidence_status in {COST_STATUS_STRUCTURED, COST_STATUS_SYNTHETIC} and any(
            value is None
            for value in (
                self.baseline_expert_calls,
                self.baseline_total_tokens,
                self.baseline_wall_ms,
            )
        ):
            raise ValueError("complete cost evidence requires calls, tokens, and wall time")
        if self.schema_version != ROUTING_OBSERVATION_SCHEMA:
            raise ValueError("unsupported selective compute observation schema")
        if self.observation_fingerprint != canonical_hash(self.payload_without_observation_fingerprint()):
            raise ValueError("selective compute observation fingerprint mismatch")

    @classmethod
    def create(cls, **kwargs: Any) -> "SelectiveComputeObservation":
        payload = dict(kwargs)
        payload.pop("observation_fingerprint", None)
        payload.setdefault("schema_version", ROUTING_OBSERVATION_SCHEMA)
        bindings = payload.get("binding_digests")
        if isinstance(bindings, Mapping):
            payload["binding_digests"] = tuple(
                BindingDigest(name=name, sha256=value)
                for name, value in sorted(bindings.items())
            )
        else:
            payload["binding_digests"] = tuple(bindings or ())
        raw = {
            **payload,
            "binding_digests": [item.to_dict() for item in payload["binding_digests"]],
        }
        return cls(**payload, observation_fingerprint=canonical_hash(raw))

    def payload_without_observation_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "publication_scope_id": self.publication_scope_id,
            "attempt_run_id": self.attempt_run_id,
            "input_index": self.input_index,
            "post_id": self.post_id,
            "binding_digests": [item.to_dict() for item in self.binding_digests],
            "publication_input_fingerprint": self.publication_input_fingerprint,
            "baseline_decision_fingerprint": self.baseline_decision_fingerprint,
            "baseline_publication_before_fingerprint": self.baseline_publication_before_fingerprint,
            "baseline_publication_after_fingerprint": self.baseline_publication_after_fingerprint,
            "candidate_set_before_fingerprint": self.candidate_set_before_fingerprint,
            "candidate_set_after_fingerprint": self.candidate_set_after_fingerprint,
            "source_binding_status": self.source_binding_status,
            "search_requirement_status": self.search_requirement_status,
            "search_health_status": self.search_health_status,
            "producer_proof_status": self.producer_proof_status,
            "candidate_generation_status": self.candidate_generation_status,
            "candidate_conflict_status": self.candidate_conflict_status,
            "vlm_ocr_requirement_status": self.vlm_ocr_requirement_status,
            "vlm_ocr_status": self.vlm_ocr_status,
            "publication_status": self.publication_status,
            "judge_coverage_status": self.judge_coverage_status,
            "scope_status": self.scope_status,
            "calibration_status": self.calibration_status,
            "budget_binding_status": self.budget_binding_status,
            "cheap_terminal_status": self.cheap_terminal_status,
            "proposed_terminal_action": self.proposed_terminal_action,
            "proposed_selected_label": self.proposed_selected_label,
            "cost_evidence_status": self.cost_evidence_status,
            "cost_evidence_digest": self.cost_evidence_digest,
            "baseline_expert_calls": self.baseline_expert_calls,
            "baseline_total_tokens": self.baseline_total_tokens,
            "baseline_wall_ms": self.baseline_wall_ms,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload_without_observation_fingerprint(),
            "observation_fingerprint": self.observation_fingerprint,
        }


def selective_compute_observation_from_dict(value: Any) -> SelectiveComputeObservation:
    if not isinstance(value, Mapping):
        raise ValueError("selective compute observation must be an object")
    expected = set(SelectiveComputeObservation.__dataclass_fields__)  # type: ignore[attr-defined]
    _require_exact_keys(value, expected, "selective compute observation")
    return SelectiveComputeObservation(
        **{
            **dict(value),
            "binding_digests": tuple(
                binding_digest_from_dict(item) for item in value["binding_digests"]
            ),
        }
    )


def _derive_hard_risks(
    observation: SelectiveComputeObservation,
    policy: SelectiveComputePolicy,
) -> Tuple[str, ...]:
    risks: set[str] = set()
    if policy.evidence_scope != EVIDENCE_SCOPE_SYNTHETIC:
        # v1 has exact saved-artifact replay in its harness, but no reusable
        # typed source-readback receipt for arbitrary actual observations.
        # Therefore actual scopes cannot become cheap merely by self-asserting
        # VALID digest strings.
        risks.add("ACTUAL_SOURCE_READBACK_NOT_IMPLEMENTED")
    if observation.source_binding_status != "VALID":
        risks.add("SOURCE_BINDING_INVALID")
    if observation.search_requirement_status == "UNKNOWN":
        risks.add("SEARCH_REQUIRED_OR_UNKNOWN")
    if observation.search_health_status in {"DEGRADED", "BLOCKED", "UNKNOWN"} or (
        observation.search_requirement_status == "REQUIRED"
        and observation.search_health_status != "HEALTHY"
    ):
        risks.add("SEARCH_DEGRADED_OR_BLOCKED")
    if observation.producer_proof_status != "COMPLETE":
        risks.add("PRODUCER_PROOF_NOT_COMPLETE")
    if observation.candidate_generation_status == "UNKNOWN":
        risks.add("CANDIDATE_GENERATION_UNKNOWN")
    elif observation.candidate_generation_status == "TRUNCATED":
        risks.add("CANDIDATE_GENERATION_TRUNCATED")
    if observation.candidate_conflict_status != "NONE":
        risks.add("MULTI_WORK_OR_IDENTITY_CONFLICT")
    if observation.vlm_ocr_status == "CONFLICT":
        risks.add("VLM_OCR_TITLE_CONFLICT")
    if observation.vlm_ocr_requirement_status == "UNKNOWN" or (
        observation.vlm_ocr_requirement_status == "REQUIRED"
        and observation.vlm_ocr_status != "COMPLETE"
    ):
        risks.add("VLM_OCR_REQUIRED_NOT_COMPLETE")
    if observation.publication_status != "CLEAN":
        risks.add("PUBLICATION_HOLD_OR_QUARANTINE")
    if observation.judge_coverage_status != "COMPLETE":
        risks.add("UNJUDGED_OR_INVALID_VERDICT")
    if observation.scope_status != "CURRENT_WORK":
        risks.add("SCOPE_UNKNOWN_OR_NOT_CURRENT_WORK")
    required_calibration = (
        "SYNTHETIC_BOUND"
        if policy.evidence_scope == EVIDENCE_SCOPE_SYNTHETIC
        else "FROZEN_ACTUAL_BOUND"
    )
    if observation.calibration_status != required_calibration:
        risks.add("CALIBRATION_ACTUAL_NOT_BOUND")
    if observation.budget_binding_status != "VALID":
        risks.add("BUDGET_SCOPE_INVALID")
    if observation.cheap_terminal_status not in {
        "VERIFIED_DETERMINISTIC_NIL",
        "VERIFIED_DETERMINISTIC_RESOLVE",
    }:
        risks.add("CHEAP_TERMINAL_NOT_VERIFIED")
    return tuple(sorted(risks))


@dataclass(frozen=True)
class SelectiveComputeRoutingReceipt:
    publication_scope_id: str
    attempt_run_id: str
    input_index: int
    post_id: str
    observation_fingerprint: str
    policy_sha256: str
    publication_input_fingerprint: str
    baseline_decision_fingerprint: str
    baseline_publication_fingerprint: str
    candidate_set_fingerprint: str
    selected_compute_lane: str
    hard_risk_codes: Tuple[str, ...]
    proposed_terminal_action: str
    proposed_selected_label: Optional[str]
    cost_metric_status: str
    baseline_expert_calls: Optional[int]
    shadow_expert_calls: Optional[int]
    expert_call_units_avoided: Optional[int]
    route_applied: bool
    action_applied: bool
    operational_effect: str
    public_decision_changed: bool
    candidate_set_changed: bool
    receipt_sha256: str
    schema_version: str = ROUTING_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        for field_name in ("publication_scope_id", "attempt_run_id", "post_id"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        _strict_nonnegative_int(self.input_index, "input_index")
        for field_name in (
            "observation_fingerprint",
            "policy_sha256",
            "publication_input_fingerprint",
            "baseline_decision_fingerprint",
            "baseline_publication_fingerprint",
            "candidate_set_fingerprint",
            "receipt_sha256",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "selected_compute_lane",
            _require_choice(
                self.selected_compute_lane,
                "selected_compute_lane",
                (LANE_FULL_EXPERT, LANE_CHEAP_RULE),
            ),
        )
        object.__setattr__(self, "hard_risk_codes", _sorted_unique(self.hard_risk_codes))
        if not set(self.hard_risk_codes).issubset(HARD_RISK_CODES):
            raise ValueError("receipt contains unregistered hard-risk code")
        if self.selected_compute_lane == LANE_FULL_EXPERT and not self.hard_risk_codes:
            raise ValueError("full-expert lane requires a hard-risk reason")
        if self.selected_compute_lane == LANE_CHEAP_RULE and self.hard_risk_codes:
            raise ValueError("cheap lane cannot contain a hard-risk reason")
        if self.selected_compute_lane == LANE_CHEAP_RULE:
            if self.proposed_terminal_action not in {ACTION_RESOLVE, ACTION_ASSERT_NIL}:
                raise ValueError("cheap lane requires a verified terminal action")
            if self.proposed_selected_label is None:
                raise ValueError("cheap lane requires a proposed label")
        elif self.proposed_terminal_action != ACTION_NONE or self.proposed_selected_label is not None:
            raise ValueError("full-expert lane must not bypass expert judgment")
        object.__setattr__(
            self,
            "cost_metric_status",
            _require_choice(
                self.cost_metric_status,
                "cost_metric_status",
                (
                    "ESTIMABLE_STRUCTURED",
                    "SYNTHETIC_CONTRACT_ONLY",
                    "NOT_ESTIMABLE",
                ),
            ),
        )
        costs = (
            self.baseline_expert_calls,
            self.shadow_expert_calls,
            self.expert_call_units_avoided,
        )
        if self.cost_metric_status == "NOT_ESTIMABLE":
            if any(value is not None for value in costs):
                raise ValueError("non-estimable cost receipt must keep numeric metrics null")
        else:
            for field_name, value in zip(
                ("baseline_expert_calls", "shadow_expert_calls", "expert_call_units_avoided"),
                costs,
            ):
                _strict_nonnegative_int(value, field_name)
            if self.expert_call_units_avoided != self.baseline_expert_calls - self.shadow_expert_calls:
                raise ValueError("expert call avoidance arithmetic mismatch")
        for field_name in ("route_applied", "action_applied"):
            if _strict_bool(getattr(self, field_name), field_name):
                raise ValueError("selective compute receipt must not apply its route or action")
        if self.operational_effect != SHADOW_OPERATIONAL_EFFECT:
            raise ValueError("routing receipt operational effect mismatch")
        if _strict_bool(self.public_decision_changed, "public_decision_changed"):
            raise ValueError("routing receipt changed public decision")
        if _strict_bool(self.candidate_set_changed, "candidate_set_changed"):
            raise ValueError("routing receipt changed candidate set")
        if self.schema_version != ROUTING_RECEIPT_SCHEMA:
            raise ValueError("unsupported routing receipt schema")
        if self.receipt_sha256 != canonical_hash(self.payload_without_receipt_sha256()):
            raise ValueError("routing receipt fingerprint mismatch")

    def payload_without_receipt_sha256(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "publication_scope_id": self.publication_scope_id,
            "attempt_run_id": self.attempt_run_id,
            "input_index": self.input_index,
            "post_id": self.post_id,
            "observation_fingerprint": self.observation_fingerprint,
            "policy_sha256": self.policy_sha256,
            "publication_input_fingerprint": self.publication_input_fingerprint,
            "baseline_decision_fingerprint": self.baseline_decision_fingerprint,
            "baseline_publication_fingerprint": self.baseline_publication_fingerprint,
            "candidate_set_fingerprint": self.candidate_set_fingerprint,
            "selected_compute_lane": self.selected_compute_lane,
            "hard_risk_codes": list(self.hard_risk_codes),
            "proposed_terminal_action": self.proposed_terminal_action,
            "proposed_selected_label": self.proposed_selected_label,
            "cost_metric_status": self.cost_metric_status,
            "baseline_expert_calls": self.baseline_expert_calls,
            "shadow_expert_calls": self.shadow_expert_calls,
            "expert_call_units_avoided": self.expert_call_units_avoided,
            "route_applied": self.route_applied,
            "action_applied": self.action_applied,
            "operational_effect": self.operational_effect,
            "public_decision_changed": self.public_decision_changed,
            "candidate_set_changed": self.candidate_set_changed,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_receipt_sha256(), "receipt_sha256": self.receipt_sha256}


def build_selective_compute_routing(
    observation: SelectiveComputeObservation,
    policy: SelectiveComputePolicy,
    *,
    decision_cost_trace: Optional[DecisionCostTrace] = None,
) -> SelectiveComputeRoutingReceipt:
    if observation.evidence_scope != policy.evidence_scope:
        raise ValueError("observation/policy evidence scope mismatch")
    if observation.cost_evidence_status in {COST_STATUS_PARTIAL_RUNTIME, COST_STATUS_STRUCTURED}:
        if decision_cost_trace is None:
            raise ValueError("runtime cost status requires its typed trace")
        if decision_cost_trace.post_id != observation.post_id:
            raise ValueError("cost trace post binding mismatch")
        if decision_cost_trace.publication_scope_id != observation.publication_scope_id:
            raise ValueError("cost trace publication scope binding mismatch")
        if decision_cost_trace.input_index != observation.input_index:
            raise ValueError("cost trace input-index binding mismatch")
        if decision_cost_trace.run_id != observation.attempt_run_id:
            raise ValueError("cost trace run binding mismatch")
        if decision_cost_trace.trace_sha256 != observation.cost_evidence_digest:
            raise ValueError("cost trace digest binding mismatch")
        if observation.baseline_total_tokens != decision_cost_trace.total_tokens:
            raise ValueError("cost trace token binding mismatch")
        if observation.baseline_wall_ms != decision_cost_trace.wall_ms:
            raise ValueError("cost trace wall binding mismatch")
        if observation.cost_evidence_status == COST_STATUS_STRUCTURED:
            if decision_cost_trace.measurement_status != COST_STATUS_STRUCTURED:
                raise ValueError("structured cost status requires complete call events")
            if observation.baseline_expert_calls != decision_cost_trace.expert_calls:
                raise ValueError("cost trace call binding mismatch")
        elif decision_cost_trace.measurement_status != COST_STATUS_PARTIAL_RUNTIME:
            raise ValueError("partial runtime cost status mismatch")
    risks = _derive_hard_risks(observation, policy)
    lane = LANE_FULL_EXPERT if risks else LANE_CHEAP_RULE
    if lane == LANE_CHEAP_RULE:
        proposed_action = observation.proposed_terminal_action
        proposed_label = observation.proposed_selected_label
    else:
        proposed_action = ACTION_NONE
        proposed_label = None
    if (
        policy.evidence_scope == EVIDENCE_SCOPE_SYNTHETIC
        and observation.cost_evidence_status == COST_STATUS_SYNTHETIC
    ):
        cost_status = "SYNTHETIC_CONTRACT_ONLY"
    else:
        cost_status = "NOT_ESTIMABLE"
    if cost_status == "NOT_ESTIMABLE":
        baseline_calls = shadow_calls = avoided = None
    else:
        baseline_calls = int(observation.baseline_expert_calls or 0)
        shadow_calls = policy.cheap_lane_expert_calls if lane == LANE_CHEAP_RULE else baseline_calls
        avoided = baseline_calls - shadow_calls
    payload = {
        "schema_version": ROUTING_RECEIPT_SCHEMA,
        "publication_scope_id": observation.publication_scope_id,
        "attempt_run_id": observation.attempt_run_id,
        "input_index": observation.input_index,
        "post_id": observation.post_id,
        "observation_fingerprint": observation.observation_fingerprint,
        "policy_sha256": policy.policy_sha256,
        "publication_input_fingerprint": observation.publication_input_fingerprint,
        "baseline_decision_fingerprint": observation.baseline_decision_fingerprint,
        "baseline_publication_fingerprint": observation.baseline_publication_before_fingerprint,
        "candidate_set_fingerprint": observation.candidate_set_before_fingerprint,
        "selected_compute_lane": lane,
        "hard_risk_codes": tuple(risks),
        "proposed_terminal_action": proposed_action,
        "proposed_selected_label": proposed_label,
        "cost_metric_status": cost_status,
        "baseline_expert_calls": baseline_calls,
        "shadow_expert_calls": shadow_calls,
        "expert_call_units_avoided": avoided,
        "route_applied": False,
        "action_applied": False,
        "operational_effect": SHADOW_OPERATIONAL_EFFECT,
        "public_decision_changed": False,
        "candidate_set_changed": False,
    }
    return SelectiveComputeRoutingReceipt(
        **payload,
        receipt_sha256=canonical_hash(payload),
    )


def selective_compute_routing_receipt_from_dict(value: Any) -> SelectiveComputeRoutingReceipt:
    if not isinstance(value, Mapping):
        raise ValueError("selective compute receipt must be an object")
    expected = set(SelectiveComputeRoutingReceipt.__dataclass_fields__)  # type: ignore[attr-defined]
    _require_exact_keys(value, expected, "selective compute receipt")
    return SelectiveComputeRoutingReceipt(
        **{**dict(value), "hard_risk_codes": tuple(value["hard_risk_codes"])}
    )


def _metric(
    *,
    value: Optional[float],
    status: str,
    numerator: Optional[int] = None,
    denominator: Optional[int] = None,
    unit: str,
) -> dict[str, Any]:
    if value is not None and (isinstance(value, bool) or not math.isfinite(float(value))):
        raise ValueError("metric value must be finite or null")
    return {
        "value": value,
        "status": status,
        "numerator": numerator,
        "denominator": denominator,
        "unit": unit,
    }


def evaluate_selective_compute_receipts(
    receipts: Sequence[SelectiveComputeRoutingReceipt],
    observations: Sequence[SelectiveComputeObservation],
    policy: SelectiveComputePolicy,
    *,
    truth_labels: Optional[Mapping[str, str]] = None,
    actual_evidence_readback: bool = False,
    decision_cost_traces: Optional[Mapping[str, DecisionCostTrace]] = None,
) -> dict[str, Any]:
    if not isinstance(actual_evidence_readback, bool):
        raise ValueError("actual_evidence_readback must be bool")
    receipt_snapshot = tuple(receipts)
    observation_snapshot = tuple(observations)
    truth_snapshot = dict(truth_labels or {})
    trace_snapshot = dict(decision_cost_traces or {})
    if not receipt_snapshot or len(receipt_snapshot) != len(observation_snapshot):
        raise ValueError("evaluation requires aligned non-empty receipt/observation rows")
    if len({item.publication_scope_id for item in receipt_snapshot}) != 1:
        raise ValueError("evaluation cannot mix publication scopes")
    if len({item.attempt_run_id for item in receipt_snapshot}) != 1:
        raise ValueError("evaluation cannot mix attempt runs")
    if len({item.post_id for item in receipt_snapshot}) != len(receipt_snapshot):
        raise ValueError("evaluation post_id values must be unique within one scope")
    observations_by_fingerprint = {item.observation_fingerprint: item for item in observation_snapshot}
    if len(observations_by_fingerprint) != len(observation_snapshot):
        raise ValueError("duplicate observation fingerprint")
    identities: set[tuple[str, int, str]] = set()
    rebuilt: list[SelectiveComputeRoutingReceipt] = []
    for receipt in receipt_snapshot:
        identity = (receipt.publication_scope_id, receipt.input_index, receipt.post_id)
        if identity in identities:
            raise ValueError("duplicate publication scope/input/post identity")
        identities.add(identity)
        observation = observations_by_fingerprint.get(receipt.observation_fingerprint)
        if observation is None:
            raise ValueError("receipt observation binding missing")
        trace = trace_snapshot.get(receipt.post_id)
        expected = build_selective_compute_routing(
            observation,
            policy,
            decision_cost_trace=trace,
        )
        if expected.to_dict() != receipt.to_dict():
            raise ValueError("routing receipt does not replay from bound observation/policy")
        rebuilt.append(expected)
    receipt_by_post = {item.post_id: item for item in rebuilt}
    lane_counts = {
        LANE_FULL_EXPERT: sum(item.selected_compute_lane == LANE_FULL_EXPERT for item in rebuilt),
        LANE_CHEAP_RULE: sum(item.selected_compute_lane == LANE_CHEAP_RULE for item in rebuilt),
    }
    risk_counts = {
        code: sum(code in item.hard_risk_codes for item in rebuilt)
        for code in HARD_RISK_CODES
        if any(code in item.hard_risk_codes for item in rebuilt)
    }
    hard_risk_cheap = sum(
        item.selected_compute_lane == LANE_CHEAP_RULE and bool(item.hard_risk_codes)
        for item in rebuilt
    )
    public_changes = sum(item.public_decision_changed for item in rebuilt)
    candidate_changes = sum(item.candidate_set_changed for item in rebuilt)
    applied = sum(item.route_applied or item.action_applied for item in rebuilt)
    # FROZEN_ACTUAL conversion remains deliberately disabled in v1.  A boolean
    # flag is not an artifact readback receipt and can never unlock metrics.
    metric_scope_allowed = policy.evidence_scope == EVIDENCE_SCOPE_SYNTHETIC
    labels_complete = bool(truth_snapshot) and set(truth_snapshot) == set(receipt_by_post)
    if metric_scope_allowed and labels_complete:
        selected = [item for item in rebuilt if item.selected_compute_lane == LANE_CHEAP_RULE]
        correct = sum(
            item.proposed_selected_label == truth_snapshot[item.post_id]
            for item in selected
        )
        safe_coverage = _metric(
            value=correct / len(rebuilt),
            status="SYNTHETIC_CONTRACT_ONLY",
            numerator=correct,
            denominator=len(rebuilt),
            unit="row_ratio",
        )
        false_safe = len(selected) - correct
    else:
        safe_coverage = _metric(
            value=None,
            status="NOT_ESTIMABLE",
            numerator=None,
            denominator=None,
            unit="row_ratio",
        )
        false_safe = None
    escalation = _metric(
        value=lane_counts[LANE_FULL_EXPERT] / len(rebuilt),
        status=(
            "SYNTHETIC_CONTRACT_ONLY"
            if policy.evidence_scope == EVIDENCE_SCOPE_SYNTHETIC
            else "OBSERVED_SHADOW_ROUTE_DISTRIBUTION"
        ),
        numerator=lane_counts[LANE_FULL_EXPERT],
        denominator=len(rebuilt),
        unit="row_ratio",
    )
    cost_complete = metric_scope_allowed and all(
        item.cost_metric_status in {"ESTIMABLE_STRUCTURED", "SYNTHETIC_CONTRACT_ONLY"}
        for item in rebuilt
    )
    if cost_complete:
        baseline_calls = sum(int(item.baseline_expert_calls or 0) for item in rebuilt)
        shadow_calls = sum(int(item.shadow_expert_calls or 0) for item in rebuilt)
        avoided = baseline_calls - shadow_calls
        calls_per_post = _metric(
            value=shadow_calls / len(rebuilt),
            status="SYNTHETIC_CONTRACT_ONLY",
            numerator=shadow_calls,
            denominator=len(rebuilt),
            unit="expert_calls_per_post",
        )
        avoidance = _metric(
            value=(avoided / baseline_calls if baseline_calls else 0.0),
            status=calls_per_post["status"],
            numerator=avoided,
            denominator=baseline_calls,
            unit="expert_call_ratio",
        )
    else:
        calls_per_post = _metric(
            value=None,
            status="NOT_ESTIMABLE",
            unit="expert_calls_per_post",
        )
        avoidance = _metric(
            value=None,
            status="NOT_ESTIMABLE",
            unit="expert_call_ratio",
        )
    wall_time = _metric(
        value=None,
        status="NOT_ESTIMABLE_NO_AFTER_RUNTIME",
        unit="milliseconds_per_post",
    )
    violations = {
        "hard_risk_routed_cheap": hard_risk_cheap,
        "public_decision_changed": public_changes,
        "candidate_set_changed": candidate_changes,
        "route_or_action_applied": applied,
        "false_safe_rows": false_safe,
    }
    contract_violations = sum(
        int(value or 0)
        for name, value in violations.items()
        if name != "false_safe_rows"
    )
    if policy.evidence_scope == EVIDENCE_SCOPE_SYNTHETIC:
        gate = "GO_SYNTHETIC_CONTRACT_ONLY" if contract_violations == 0 and false_safe == 0 else "NO_GO"
    elif policy.evidence_scope == EVIDENCE_SCOPE_FROZEN_ACTUAL and actual_evidence_readback:
        gate = "NO_GO_ACTUAL_ARTIFACT_READBACK_NOT_IMPLEMENTED"
    else:
        gate = "NO_GO_ACTUAL_EVIDENCE_NOT_AVAILABLE"
    return {
        "schema_version": ROUTING_EVALUATION_SCHEMA,
        "evidence_scope": policy.evidence_scope,
        "policy_sha256": policy.policy_sha256,
        "row_count": len(rebuilt),
        "lane_counts": lane_counts,
        "hard_risk_counts": risk_counts,
        "primary_metrics": {
            "safe_auto_coverage": safe_coverage,
            "expert_escalation_rate": escalation,
            "expert_calls_per_post": calls_per_post,
            "expert_call_avoidance_rate": avoidance,
            "wall_time_per_post": wall_time,
        },
        "guardrail_violations": violations,
        "actual_evidence_readback": actual_evidence_readback,
        "gate": gate,
        "runtime_validation": "NOT_RUN",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
