"""Typed CandidateSet/NIL shadow contracts.

This module is deliberately outside the publication-input contract.  It may
observe a frozen promotion contract and candidate-bearing fields, but it never
changes ``GroundingState``, ``PromotionDecision``, public title/URL, or the v2
publication fingerprint.  Probabilities remain unavailable until an external,
frozen calibration set exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

from .candidate_generation import (
    CANDIDATE_GENERATION_VERSION,
    TITLE_CANDIDATE_GENERATION_VERSION,
    build_candidate_generation_proof,
    candidate_generation_proof_from_dict,
    candidate_generation_snapshot_from_dict,
    candidate_producer_plans_from_payload,
    candidate_producer_receipts_from_payload,
)
from .promotion_gate import (
    EvidenceRecord,
    GroundingState,
    PromotionDecision,
    RetrievalState,
    _canonical_url,
    _title_key,
    can_publish_title,
    evidence_records_from_payload,
    grounding_state_from_dict,
)


CANDIDATE_SET_VERSION = "candidate_set_v1"
SELECTIVE_SHADOW_VERSION = "candidate_set_nil_shadow_v1"
SELECTIVE_SHADOW_UNAVAILABLE_VERSION = "candidate_set_nil_shadow_unavailable_v1"
NIL_LABEL = "__NIL__"
PROBABILITY_STATUS = "NOT_AVAILABLE_UNCALIBRATED"
CALIBRATED_SHADOW_STATUS = "CALIBRATED_SHADOW"
SHADOW_ACTION_ABSTAIN = "ABSTAIN"
SHADOW_ACTION_NOT_EVALUATED = "NOT_EVALUATED"
SHADOW_ACTION_RESOLVE = "RESOLVE"
SHADOW_ACTION_ASSERT_NIL = "ASSERT_NIL"
SHADOW_OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"

_CANDIDATE_SOURCE_FIELDS = (
    "primary_work",
    "title_candidates",
    "mentioned_works",
    "secondary_reference_works",
    "comparison_target",
    "future_watch_target",
    "recommendation_candidates",
    "candidate_preservation_sources",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def _dedupe_sorted(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(sorted({str(value or "").strip() for value in values if str(value or "").strip()}))


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a bool")
    return value


def _strict_nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative int")
    return value


def _strict_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple")
    return value


def _require_sha256(value: Any, field_name: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"{field_name} must be a sha256 hex digest")
    return text


@dataclass(frozen=True)
class CandidateOption:
    candidate_id: str
    titles: Tuple[str, ...]
    urls: Tuple[str, ...] = field(default_factory=tuple)
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    option_kind: str = "WORK_CANDIDATE"
    event_eligible: bool = True
    source_fields: Tuple[str, ...] = field(default_factory=tuple)
    evidence_kinds: Tuple[str, ...] = field(default_factory=tuple)
    source_tiers: Tuple[str, ...] = field(default_factory=tuple)
    reference_roles: Tuple[str, ...] = field(default_factory=tuple)
    preservation_roles: Tuple[str, ...] = field(default_factory=tuple)
    promotion_policies: Tuple[str, ...] = field(default_factory=tuple)
    local_preservation_types: Tuple[str, ...] = field(default_factory=tuple)
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    negative_evidence: Tuple[str, ...] = field(default_factory=tuple)
    baseline_selected: bool = False
    publish_support_present: bool = False
    identity_conflict: bool = False

    def __post_init__(self) -> None:
        if not str(self.candidate_id or "").strip() or self.candidate_id == NIL_LABEL:
            raise ValueError("candidate_id must be non-empty and must not equal NIL")
        for field_name in (
            "titles",
            "urls",
            "aliases",
            "source_fields",
            "evidence_kinds",
            "source_tiers",
            "reference_roles",
            "preservation_roles",
            "promotion_policies",
            "local_preservation_types",
            "reason_codes",
            "negative_evidence",
        ):
            values = tuple(getattr(self, field_name))
            if values != _dedupe_sorted(values):
                raise ValueError(f"{field_name} must be sorted and unique")
            object.__setattr__(self, field_name, values)
        if not self.titles and not self.urls:
            raise ValueError("candidate option must contain a title or URL")
        if self.candidate_id != _candidate_id(self.titles, self.urls):
            raise ValueError("candidate_id does not match canonical title/URL identity")
        if self.option_kind not in {
            "WORK_CANDIDATE",
            "UNLINKED_SURFACE",
            "OBSERVED_LATE_SURFACE",
        }:
            raise ValueError("unsupported candidate option kind")
        if self.option_kind != "WORK_CANDIDATE" and self.event_eligible:
            raise ValueError("non-work observations must not enter the probability event space")
        if self.identity_conflict and self.event_eligible:
            raise ValueError("identity-conflicted candidates must not enter the probability event space")
        for field_name in (
            "event_eligible",
            "baseline_selected",
            "publish_support_present",
            "identity_conflict",
        ):
            _strict_bool(getattr(self, field_name), field_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "titles": list(self.titles),
            "urls": list(self.urls),
            "aliases": list(self.aliases),
            "option_kind": self.option_kind,
            "event_eligible": self.event_eligible,
            "source_fields": list(self.source_fields),
            "evidence_kinds": list(self.evidence_kinds),
            "source_tiers": list(self.source_tiers),
            "reference_roles": list(self.reference_roles),
            "preservation_roles": list(self.preservation_roles),
            "promotion_policies": list(self.promotion_policies),
            "local_preservation_types": list(self.local_preservation_types),
            "reason_codes": list(self.reason_codes),
            "negative_evidence": list(self.negative_evidence),
            "baseline_selected": self.baseline_selected,
            "publish_support_present": self.publish_support_present,
            "identity_conflict": self.identity_conflict,
        }

    def identity_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "titles": list(self.titles),
            "urls": list(self.urls),
            "aliases": list(self.aliases),
            "option_kind": self.option_kind,
            "event_eligible": self.event_eligible,
            "identity_conflict": self.identity_conflict,
        }


@dataclass(frozen=True)
class CandidateSet:
    candidates: Tuple[CandidateOption, ...]
    source_record_count: int
    source_candidate_pair_count: int
    typed_inventory_pair_count: int
    candidate_inventory_count_hint: int
    work_candidate_count: int
    unlinked_surface_count: int
    observed_late_surface_count: int
    event_candidate_count: int
    generation_status: str
    generation_cap: Optional[int]
    candidate_set_recall_status: str
    observation_signatures: Tuple[str, ...]
    integrity_status: str
    reason_codes: Tuple[str, ...]
    candidate_set_fingerprint: str
    observation_fingerprint: str
    nil_label: str = NIL_LABEL
    schema_version: str = CANDIDATE_SET_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        ids = [candidate.candidate_id for candidate in self.candidates]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("candidate ids must be sorted and unique")
        for field_name in (
            "source_record_count",
            "source_candidate_pair_count",
            "typed_inventory_pair_count",
            "candidate_inventory_count_hint",
            "work_candidate_count",
            "unlinked_surface_count",
            "observed_late_surface_count",
            "event_candidate_count",
        ):
            _strict_nonnegative_int(getattr(self, field_name), field_name)
        if self.integrity_status not in {"GO", "NO-GO"}:
            raise ValueError("integrity_status must be GO or NO-GO")
        if tuple(self.reason_codes) != _dedupe_sorted(self.reason_codes):
            raise ValueError("reason_codes must be sorted and unique")
        if self.nil_label != NIL_LABEL:
            raise ValueError("nil_label must use the reserved NIL label")
        if self.schema_version != CANDIDATE_SET_VERSION:
            raise ValueError("unsupported candidate-set schema version")
        _require_sha256(self.candidate_set_fingerprint, "candidate_set_fingerprint")
        _require_sha256(self.observation_fingerprint, "observation_fingerprint")
        if self.work_candidate_count != sum(
            candidate.option_kind == "WORK_CANDIDATE" for candidate in self.candidates
        ):
            raise ValueError("work_candidate_count mismatch")
        if self.unlinked_surface_count != sum(
            candidate.option_kind == "UNLINKED_SURFACE" for candidate in self.candidates
        ):
            raise ValueError("unlinked_surface_count mismatch")
        if self.observed_late_surface_count != sum(
            candidate.option_kind == "OBSERVED_LATE_SURFACE" for candidate in self.candidates
        ):
            raise ValueError("observed_late_surface_count mismatch")
        if self.event_candidate_count != sum(candidate.event_eligible for candidate in self.candidates):
            raise ValueError("event_candidate_count mismatch")
        if self.generation_status not in {"COMPLETE", "TRUNCATED", "UNKNOWN"}:
            raise ValueError("unsupported generation_status")
        expected_recall = (
            "READY_FOR_GOLD_EVALUATION"
            if self.generation_status == "COMPLETE"
            else f"NOT_EVALUABLE_GENERATION_{self.generation_status}"
        )
        if self.candidate_set_recall_status != expected_recall:
            raise ValueError("candidate_set_recall_status mismatch")
        if self.generation_cap is not None:
            _strict_nonnegative_int(self.generation_cap, "generation_cap")
            if self.generation_cap <= 0:
                raise ValueError("generation_cap must be positive when provided")
        if self.generation_status == "TRUNCATED" and self.generation_cap is None:
            raise ValueError("TRUNCATED generation requires generation_cap")
        if (
            self.generation_status == "COMPLETE"
            and self.generation_cap is not None
            and self.source_record_count >= self.generation_cap
        ):
            raise ValueError("generation at cap cannot be declared COMPLETE")
        object.__setattr__(self, "observation_signatures", tuple(self.observation_signatures))
        if self.observation_signatures != tuple(sorted(self.observation_signatures)):
            raise ValueError("observation_signatures must be sorted")
        for signature in self.observation_signatures:
            _require_sha256(signature, "observation_signature")
        if len(self.observation_signatures) != self.source_record_count:
            raise ValueError("source_record_count/observation_signatures mismatch")
        if _canonical_hash(self.identity_payload()) != self.candidate_set_fingerprint:
            raise ValueError("candidate_set_fingerprint mismatch")
        if (
            _canonical_hash(self.observation_payload_without_fingerprints())
            != self.observation_fingerprint
        ):
            raise ValueError("observation_fingerprint mismatch")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "nil_label": self.nil_label,
            "candidates": [candidate.identity_dict() for candidate in self.candidates],
            "generation_status": self.generation_status,
            "generation_cap": self.generation_cap,
            "candidate_set_recall_status": self.candidate_set_recall_status,
        }

    def observation_payload_without_fingerprints(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "nil_label": self.nil_label,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "source_record_count": self.source_record_count,
            "source_candidate_pair_count": self.source_candidate_pair_count,
            "typed_inventory_pair_count": self.typed_inventory_pair_count,
            "candidate_inventory_count_hint": self.candidate_inventory_count_hint,
            "work_candidate_count": self.work_candidate_count,
            "unlinked_surface_count": self.unlinked_surface_count,
            "observed_late_surface_count": self.observed_late_surface_count,
            "event_candidate_count": self.event_candidate_count,
            "generation_status": self.generation_status,
            "generation_cap": self.generation_cap,
            "candidate_set_recall_status": self.candidate_set_recall_status,
            "observation_signatures": list(self.observation_signatures),
            "integrity_status": self.integrity_status,
            "reason_codes": list(self.reason_codes),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.observation_payload_without_fingerprints(),
            "candidate_set_fingerprint": self.candidate_set_fingerprint,
            "observation_fingerprint": self.observation_fingerprint,
        }


@dataclass(frozen=True)
class LabelProbability:
    label: str
    probability: Optional[float] = None

    def __post_init__(self) -> None:
        if not str(self.label or "").strip():
            raise ValueError("probability label must be non-empty")
        if self.probability is not None:
            if isinstance(self.probability, bool) or not isinstance(self.probability, (int, float)):
                raise ValueError("probability must be numeric or null")
            if not 0.0 <= float(self.probability) <= 1.0:
                raise ValueError("probability must be within [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "probability": self.probability}


@dataclass(frozen=True)
class SelectiveShadowDecision:
    candidate_set: CandidateSet
    event_probabilities: Tuple[LabelProbability, ...]
    probability_status: str
    selected_label: Optional[str]
    action: str
    action_applied: bool
    operational_effect: str
    reason_codes: Tuple[str, ...]
    baseline_decision_fingerprint: str
    baseline_selected_candidate_id: Optional[str]
    input_fingerprint: str
    shadow_fingerprint: str
    schema_version: str = SELECTIVE_SHADOW_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_probabilities", tuple(self.event_probabilities))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        labels = [item.label for item in self.event_probabilities]
        expected = [
            candidate.candidate_id
            for candidate in self.candidate_set.candidates
            if candidate.event_eligible
        ] + [NIL_LABEL]
        if labels != expected or len(labels) != len(set(labels)):
            raise ValueError("event labels must be ordered candidate ids followed by NIL")
        values = [item.probability for item in self.event_probabilities]
        available = [value is not None for value in values]
        if any(available) and not all(available):
            raise ValueError("probabilities must be all available or all null")
        if all(available):
            if abs(sum(float(value) for value in values if value is not None) - 1.0) > 1e-9:
                raise ValueError("candidate and NIL probabilities must sum to 1")
            if self.probability_status != CALIBRATED_SHADOW_STATUS:
                raise ValueError("available probabilities require CALIBRATED_SHADOW status")
            if self.selected_label is None:
                raise ValueError("calibrated probabilities require selected_label")
        elif self.probability_status != PROBABILITY_STATUS:
            raise ValueError("all-null probabilities require uncalibrated status")
        if self.probability_status == PROBABILITY_STATUS and self.selected_label is not None:
            raise ValueError("uncalibrated shadow must not choose a truth label")
        if self.selected_label is not None and self.selected_label not in labels:
            raise ValueError("selected_label must belong to the candidate/NIL label space")
        if self.action not in {
            SHADOW_ACTION_ABSTAIN,
            SHADOW_ACTION_NOT_EVALUATED,
            SHADOW_ACTION_RESOLVE,
            SHADOW_ACTION_ASSERT_NIL,
        }:
            raise ValueError("unsupported selective shadow action")
        if self.action == SHADOW_ACTION_ABSTAIN and not set(self.reason_codes).intersection(
            {
                "candidate_set_integrity_requires_abstain",
                "retrieval_failclose_requires_abstain",
                "selective_risk_threshold_requires_abstain",
            }
        ):
            raise ValueError("ABSTAIN requires a deterministic safety blocker")
        if self.probability_status == PROBABILITY_STATUS and self.action not in {
            SHADOW_ACTION_NOT_EVALUATED,
            SHADOW_ACTION_ABSTAIN,
        }:
            raise ValueError("uncalibrated shadow cannot resolve a candidate or NIL")
        if self.action == SHADOW_ACTION_RESOLVE and self.selected_label == NIL_LABEL:
            raise ValueError("RESOLVE action requires a work-candidate label")
        if self.action == SHADOW_ACTION_ASSERT_NIL and self.selected_label != NIL_LABEL:
            raise ValueError("ASSERT_NIL action requires the NIL label")
        if _strict_bool(self.action_applied, "action_applied"):
            raise ValueError("shadow action must never be applied to publication")
        if self.operational_effect != SHADOW_OPERATIONAL_EFFECT:
            raise ValueError("shadow operational effect must be NONE_SHADOW_ONLY")
        if tuple(self.reason_codes) != _dedupe_sorted(self.reason_codes):
            raise ValueError("reason_codes must be sorted and unique")
        if self.baseline_selected_candidate_id is not None and self.baseline_selected_candidate_id not in labels[:-1]:
            raise ValueError("baseline selected candidate must belong to CandidateSet")
        if self.schema_version != SELECTIVE_SHADOW_VERSION:
            raise ValueError("unsupported selective-shadow schema version")
        for field_name in (
            "baseline_decision_fingerprint",
            "input_fingerprint",
            "shadow_fingerprint",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        if _canonical_hash(self.payload_without_shadow_fingerprint()) != self.shadow_fingerprint:
            raise ValueError("shadow_fingerprint mismatch")

    def payload_without_shadow_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_set": self.candidate_set.to_dict(),
            "event_probabilities": [item.to_dict() for item in self.event_probabilities],
            "probability_status": self.probability_status,
            "selected_label": self.selected_label,
            "action": self.action,
            "action_applied": self.action_applied,
            "operational_effect": self.operational_effect,
            "reason_codes": list(self.reason_codes),
            "baseline_decision_fingerprint": self.baseline_decision_fingerprint,
            "baseline_selected_candidate_id": self.baseline_selected_candidate_id,
            "input_fingerprint": self.input_fingerprint,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload_without_shadow_fingerprint(),
            "shadow_fingerprint": self.shadow_fingerprint,
        }


@dataclass(frozen=True)
class _Observation:
    title: str
    url: str
    source_field: str
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    evidence_kind: str = ""
    source_tier: str = ""
    reference_role: str = ""
    preservation_role: str = ""
    promotion_policy: str = ""
    local_preservation_type: str = ""
    reason_code: str = ""
    negative_evidence: Tuple[str, ...] = field(default_factory=tuple)
    baseline_selected: bool = False
    supports_publish: bool = False
    typed_inventory: bool = False
    alias_only: bool = False

    @property
    def title_key(self) -> str:
        return _title_key(self.title)

    @property
    def canonical_url(self) -> str:
        return _canonical_url(self.url)

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "title_key": self.title_key,
            "url": self.canonical_url,
            "aliases": list(self.aliases),
            "source_field": self.source_field,
            "evidence_kind": self.evidence_kind,
            "source_tier": self.source_tier,
            "reference_role": self.reference_role,
            "preservation_role": self.preservation_role,
            "promotion_policy": self.promotion_policy,
            "local_preservation_type": self.local_preservation_type,
            "reason_code": self.reason_code,
            "negative_evidence": list(self.negative_evidence),
            "baseline_selected": self.baseline_selected,
            "supports_publish": self.supports_publish,
            "typed_inventory": self.typed_inventory,
            "alias_only": self.alias_only,
        }


def _iter_source_items(value: Any) -> Iterable[Any]:
    if isinstance(value, (list, tuple)):
        for item in value:
            yield item
    elif value not in (None, ""):
        yield value


def _observation_from_source(source_field: str, item: Any) -> Optional[_Observation]:
    if isinstance(item, Mapping):
        title = str(
            item.get("candidate_title")
            or item.get("official_title")
            or item.get("official_novel_title")
            or item.get("resolved_title")
            or item.get("title")
            or ""
        ).strip()
        url = str(
            item.get("candidate_url")
            or item.get("official_url")
            or item.get("heretic_url")
            or item.get("resolved_url")
            or item.get("url")
            or ""
        ).strip()
        negative = item.get("negative_evidence")
        if negative in (None, ""):
            negative_values: Tuple[str, ...] = ()
        elif isinstance(negative, (list, tuple)):
            negative_values = _dedupe_sorted(negative)
        else:
            negative_values = (str(negative).strip(),)
        aliases = _dedupe_sorted(
            [
                item.get("alias_or_mention"),
                item.get("canonical_value") if item.get("kind") == "alias" else None,
            ]
        )
        if not title and not url and aliases:
            title = aliases[0]
        observation = _Observation(
            title=title,
            url=url,
            aliases=aliases,
            source_field=source_field,
            source_tier=str(item.get("source_tier") or "").strip(),
            reference_role=str(item.get("reference_role") or "").strip(),
            preservation_role=str(item.get("preservation_role") or "").strip(),
            promotion_policy=str(item.get("promotion_policy") or "").strip(),
            local_preservation_type=str(item.get("local_preservation_type") or "").strip(),
            reason_code=str(item.get("reason_code") or "").strip(),
            negative_evidence=negative_values,
            supports_publish=item.get("supports_publish") is True,
        )
    elif isinstance(item, str):
        observation = _Observation(title=item.strip(), url="", source_field=source_field)
    else:
        return None
    return observation if observation.title or observation.url else None


def _candidate_id(titles: Tuple[str, ...], urls: Tuple[str, ...]) -> str:
    if len(urls) == 1:
        identity = {"kind": "url", "value": urls[0]}
    elif len(urls) > 1:
        identity = {"kind": "conflict", "urls": list(urls), "titles": list(titles)}
    else:
        title_keys = sorted({_title_key(title) for title in titles if _title_key(title)})
        identity = {"kind": "title", "value": title_keys[0] if title_keys else ""}
    return f"cand_{_canonical_hash(identity)}"


def build_candidate_set(
    state: GroundingState,
    evidence: Iterable[EvidenceRecord],
    *,
    additional_sources: Iterable[tuple[str, Any]] = (),
    generation_status: str = "UNKNOWN",
    generation_cap: Optional[int] = None,
) -> CandidateSet:
    normalized_generation_status = str(generation_status or "UNKNOWN").strip().upper()
    if normalized_generation_status not in {"COMPLETE", "TRUNCATED", "UNKNOWN"}:
        raise ValueError("unsupported generation_status")
    if generation_cap is not None:
        _strict_nonnegative_int(generation_cap, "generation_cap")
    records = tuple(evidence)
    if any(not isinstance(record, EvidenceRecord) for record in records):
        raise ValueError("candidate-set evidence must contain only EvidenceRecord values")
    additional_sources = tuple(additional_sources)
    explicit_alias_keys: set[str] = set()
    for _source_field, source_value in additional_sources:
        for item in _iter_source_items(source_value):
            if not isinstance(item, Mapping):
                continue
            alias = str(item.get("alias_or_mention") or "").strip()
            alias_key = _title_key(alias)
            if not alias_key:
                continue
            linked_title = str(
                item.get("candidate_title")
                or item.get("official_title")
                or item.get("official_novel_title")
                or item.get("resolved_title")
                or item.get("title")
                or ""
            ).strip()
            policy = str(item.get("promotion_policy") or "").strip()
            preservation_role = str(item.get("preservation_role") or "").strip()
            local_type = str(item.get("local_preservation_type") or "").strip()
            if (
                (linked_title and _title_key(linked_title) != alias_key)
                or policy in {"hold_without_promotion", "preserve_only"}
                or preservation_role == "recommendation_candidate"
                or "alias_hold" in local_type
            ):
                explicit_alias_keys.add(alias_key)
    observations: list[_Observation] = []
    selected_title = str(state.candidate_title or "").strip()
    selected_url = str(state.candidate_url or "").strip()
    if selected_title or selected_url:
        observations.append(
            _Observation(
                title=selected_title,
                url=selected_url,
                source_field="promotion_gate_state",
                baseline_selected=True,
            )
        )
    for record in records:
        title = str(record.candidate_title or "").strip()
        url = str(record.candidate_url or "").strip()
        if not title and not url:
            continue
        selected = bool(
            selected_title or selected_url
        ) and _title_key(title) == _title_key(selected_title) and _canonical_url(url) == _canonical_url(selected_url)
        alias_only = bool(not url and _title_key(title) in explicit_alias_keys)
        observations.append(
            _Observation(
                title=title,
                url=url,
                source_field="promotion_gate_evidence",
                evidence_kind=str(record.kind or "").strip(),
                reason_code=str(record.reason_code or "").strip(),
                baseline_selected=selected,
                supports_publish=record.supports_publish,
                typed_inventory=record.kind == "candidate_preservation",
                alias_only=alias_only,
            )
        )
    for source_field, value in additional_sources:
        for item in _iter_source_items(value):
            observation = _observation_from_source(str(source_field), item)
            if observation is not None:
                observations.append(observation)

    parents = list(range(len(observations)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    title_only_owner: dict[str, int] = {}
    url_owner: dict[str, int] = {}
    for index, observation in enumerate(observations):
        if observation.canonical_url:
            if observation.canonical_url in url_owner:
                union(index, url_owner[observation.canonical_url])
            else:
                url_owner[observation.canonical_url] = index
        elif observation.title_key:
            if observation.title_key in title_only_owner:
                union(index, title_only_owner[observation.title_key])
            else:
                title_only_owner[observation.title_key] = index

    url_roots_by_title: dict[str, set[int]] = {}
    for index, observation in enumerate(observations):
        if observation.canonical_url and observation.title_key:
            url_roots_by_title.setdefault(observation.title_key, set()).add(find(index))
    ambiguous_title_keys: set[str] = set()
    for index, observation in enumerate(observations):
        if observation.canonical_url or not observation.title_key:
            continue
        matching_roots = url_roots_by_title.get(observation.title_key, set())
        if len(matching_roots) == 1:
            union(index, next(iter(matching_roots)))
        elif len(matching_roots) > 1:
            ambiguous_title_keys.add(observation.title_key)

    groups: dict[int, list[_Observation]] = {}
    for index, observation in enumerate(observations):
        groups.setdefault(find(index), []).append(observation)

    options: list[CandidateOption] = []
    for group in groups.values():
        titles = _dedupe_sorted(item.title for item in group)
        urls = _dedupe_sorted(item.canonical_url for item in group)
        aliases = _dedupe_sorted(alias for item in group for alias in item.aliases)
        source_fields = _dedupe_sorted(item.source_field for item in group)
        source_tiers = _dedupe_sorted(item.source_tier for item in group)
        preservation_roles = _dedupe_sorted(item.preservation_role for item in group)
        promotion_policies = _dedupe_sorted(item.promotion_policy for item in group)
        local_types = _dedupe_sorted(item.local_preservation_type for item in group)
        ambiguous_url_less_surface = bool(
            not urls
            and any(item.title_key in ambiguous_title_keys for item in group if item.title_key)
        )
        explicit_unlinked = bool(
            ambiguous_url_less_surface
            or any(item.alias_only for item in group)
            or set(promotion_policies).intersection({"hold_without_promotion", "preserve_only"})
            or "recommendation_candidate" in preservation_roles
            or any("alias_hold" in value or "hold_without_promotion" in value for value in local_types)
        )
        strong_work_signal = any(
            (item.baseline_selected or item.supports_publish or item.typed_inventory)
            and not item.alias_only
            for item in group
        )
        typed_inventory_signal = any(item.typed_inventory for item in group)
        option_kind = (
            "UNLINKED_SURFACE"
            if explicit_unlinked and not strong_work_signal
            else "WORK_CANDIDATE"
            if strong_work_signal or typed_inventory_signal
            else "OBSERVED_LATE_SURFACE"
        )
        identity_conflict = len(urls) > 1
        event_eligible = option_kind == "WORK_CANDIDATE" and not identity_conflict
        options.append(
            CandidateOption(
                candidate_id=_candidate_id(titles, urls),
                titles=titles,
                urls=urls,
                aliases=aliases,
                option_kind=option_kind,
                event_eligible=event_eligible,
                source_fields=source_fields,
                evidence_kinds=_dedupe_sorted(item.evidence_kind for item in group),
                source_tiers=source_tiers,
                reference_roles=_dedupe_sorted(item.reference_role for item in group),
                preservation_roles=preservation_roles,
                promotion_policies=promotion_policies,
                local_preservation_types=local_types,
                reason_codes=_dedupe_sorted(item.reason_code for item in group),
                negative_evidence=_dedupe_sorted(
                    value for item in group for value in item.negative_evidence
                ),
                baseline_selected=any(item.baseline_selected for item in group),
                publish_support_present=any(item.supports_publish for item in group),
                identity_conflict=identity_conflict,
            )
        )
    options.sort(key=lambda option: option.candidate_id)

    source_pairs = {
        (item.title_key, item.canonical_url)
        for item in observations
        if item.title_key or item.canonical_url
    }
    typed_pairs = {
        (item.title_key, item.canonical_url)
        for item in observations
        if item.typed_inventory and (item.title_key or item.canonical_url)
    }
    hint = state.candidate_inventory_count
    reasons: list[str] = []
    if not options:
        reasons.append("candidate_set_empty")
    if len(options) > 1:
        reasons.append("multiple_candidates_present")
    work_count = sum(option.option_kind == "WORK_CANDIDATE" for option in options)
    unlinked_count = sum(option.option_kind == "UNLINKED_SURFACE" for option in options)
    late_count = sum(option.option_kind == "OBSERVED_LATE_SURFACE" for option in options)
    event_count = sum(option.event_eligible for option in options)
    if work_count > 1:
        reasons.append("multiple_work_candidates_present")
    if unlinked_count:
        reasons.append("unlinked_surfaces_preserved_outside_event_space")
    if late_count:
        reasons.append("late_surfaces_preserved_outside_authoritative_event_space")
    if ambiguous_title_keys:
        reasons.append("ambiguous_title_alias_multiple_urls")
    if any(option.identity_conflict for option in options):
        reasons.append("candidate_identity_unresolved_multiple_urls")
    if options and not event_count:
        reasons.append("no_event_eligible_work_candidates")
    if normalized_generation_status == "UNKNOWN":
        reasons.append("candidate_generation_completeness_unknown")
    elif normalized_generation_status == "TRUNCATED":
        reasons.append("candidate_generation_truncated")
    if hint and len(typed_pairs) != hint:
        reasons.append("candidate_inventory_count_mismatch")
    selected_count = sum(1 for option in options if option.baseline_selected)
    if selected_count > 1:
        reasons.append("multiple_baseline_selected_candidates")
    if any(option.baseline_selected and not option.event_eligible for option in options):
        reasons.append("baseline_selected_candidate_not_event_eligible")
    integrity_status = (
        "NO-GO"
        if set(reasons)
        & {
            "candidate_identity_unresolved_multiple_urls",
            "candidate_inventory_count_mismatch",
            "multiple_baseline_selected_candidates",
            "baseline_selected_candidate_not_event_eligible",
        }
        else "GO"
    )
    reason_codes = _dedupe_sorted(reasons)
    recall_status = (
        "READY_FOR_GOLD_EVALUATION"
        if normalized_generation_status == "COMPLETE"
        else f"NOT_EVALUABLE_GENERATION_{normalized_generation_status}"
    )
    observation_signatures = tuple(
        sorted(_canonical_hash(item.fingerprint_payload()) for item in observations)
    )
    if generation_cap is not None and generation_cap <= 0:
        raise ValueError("generation_cap must be positive when provided")
    if normalized_generation_status == "TRUNCATED" and generation_cap is None:
        raise ValueError("TRUNCATED generation requires generation_cap")
    if (
        normalized_generation_status == "COMPLETE"
        and generation_cap is not None
        and len(observations) >= generation_cap
    ):
        raise ValueError("generation at cap cannot be declared COMPLETE")
    identity_payload = {
        "schema_version": CANDIDATE_SET_VERSION,
        "nil_label": NIL_LABEL,
        "candidates": [option.identity_dict() for option in options],
        "generation_status": normalized_generation_status,
        "generation_cap": generation_cap,
        "candidate_set_recall_status": recall_status,
    }
    observation_payload = {
        "schema_version": CANDIDATE_SET_VERSION,
        "nil_label": NIL_LABEL,
        "candidates": [option.to_dict() for option in options],
        "source_record_count": len(observations),
        "source_candidate_pair_count": len(source_pairs),
        "typed_inventory_pair_count": len(typed_pairs),
        "candidate_inventory_count_hint": hint,
        "work_candidate_count": work_count,
        "unlinked_surface_count": unlinked_count,
        "observed_late_surface_count": late_count,
        "event_candidate_count": event_count,
        "generation_status": normalized_generation_status,
        "generation_cap": generation_cap,
        "candidate_set_recall_status": recall_status,
        "observation_signatures": list(observation_signatures),
        "integrity_status": integrity_status,
        "reason_codes": list(reason_codes),
    }
    return CandidateSet(
        candidates=tuple(options),
        source_record_count=len(observations),
        source_candidate_pair_count=len(source_pairs),
        typed_inventory_pair_count=len(typed_pairs),
        candidate_inventory_count_hint=hint,
        work_candidate_count=work_count,
        unlinked_surface_count=unlinked_count,
        observed_late_surface_count=late_count,
        event_candidate_count=event_count,
        generation_status=normalized_generation_status,
        generation_cap=generation_cap,
        candidate_set_recall_status=recall_status,
        observation_signatures=observation_signatures,
        integrity_status=integrity_status,
        reason_codes=reason_codes,
        candidate_set_fingerprint=_canonical_hash(identity_payload),
        observation_fingerprint=_canonical_hash(observation_payload),
    )


def build_uncalibrated_selective_shadow(
    state: GroundingState,
    evidence: Iterable[EvidenceRecord],
    baseline_decision: PromotionDecision,
    *,
    additional_sources: Iterable[tuple[str, Any]] = (),
    generation_status: str = "UNKNOWN",
    generation_cap: Optional[int] = None,
) -> SelectiveShadowDecision:
    records = tuple(evidence)
    replay = can_publish_title(state, records)
    if _canonical_hash(baseline_decision.to_dict()) != _canonical_hash(replay.to_dict()):
        raise ValueError("baseline promotion decision does not replay exactly")
    baseline_decision = replay
    candidate_set = build_candidate_set(
        state,
        records,
        additional_sources=additional_sources,
        generation_status=generation_status,
        generation_cap=generation_cap,
    )
    probabilities = tuple(
        LabelProbability(label=candidate.candidate_id, probability=None)
        for candidate in candidate_set.candidates
        if candidate.event_eligible
    ) + (LabelProbability(label=NIL_LABEL, probability=None),)
    selected = [
        candidate.candidate_id
        for candidate in candidate_set.candidates
        if candidate.baseline_selected and candidate.event_eligible
    ]
    reasons = [
        "probability_uncalibrated",
        "shadow_action_not_applied",
        *candidate_set.reason_codes,
    ]
    if candidate_set.event_candidate_count > 1:
        reasons.append("candidate_selection_not_scored")
    retrieval_blocks = isinstance(state.retrieval, RetrievalState) and state.retrieval.blocks_publish()
    if retrieval_blocks:
        reasons.append("retrieval_failclose_requires_abstain")
    if candidate_set.integrity_status == "NO-GO":
        reasons.append("candidate_set_integrity_requires_abstain")
    action = (
        SHADOW_ACTION_ABSTAIN
        if retrieval_blocks or candidate_set.integrity_status == "NO-GO"
        else SHADOW_ACTION_NOT_EVALUATED
    )
    baseline_fingerprint = _canonical_hash(baseline_decision.to_dict())
    input_fingerprint = _canonical_hash(
        {
            "schema_version": SELECTIVE_SHADOW_VERSION,
            "candidate_set_fingerprint": candidate_set.candidate_set_fingerprint,
            "baseline_decision": baseline_decision.to_dict(),
        }
    )
    payload = {
        "schema_version": SELECTIVE_SHADOW_VERSION,
        "candidate_set": candidate_set.to_dict(),
        "event_probabilities": [item.to_dict() for item in probabilities],
        "probability_status": PROBABILITY_STATUS,
        "selected_label": None,
        "action": action,
        "action_applied": False,
        "operational_effect": SHADOW_OPERATIONAL_EFFECT,
        "reason_codes": list(_dedupe_sorted(reasons)),
        "baseline_decision_fingerprint": baseline_fingerprint,
        "baseline_selected_candidate_id": selected[0] if len(selected) == 1 else None,
        "input_fingerprint": input_fingerprint,
    }
    return SelectiveShadowDecision(
        candidate_set=candidate_set,
        event_probabilities=probabilities,
        probability_status=PROBABILITY_STATUS,
        selected_label=None,
        action=action,
        action_applied=False,
        operational_effect=SHADOW_OPERATIONAL_EFFECT,
        reason_codes=_dedupe_sorted(reasons),
        baseline_decision_fingerprint=baseline_fingerprint,
        baseline_selected_candidate_id=selected[0] if len(selected) == 1 else None,
        input_fingerprint=input_fingerprint,
        shadow_fingerprint=_canonical_hash(payload),
    )


def _identity_contract_payloads(
    identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Sequence[Any], Mapping[str, Any]]:
    ledger = identity.get("candidate_ledger")
    ledger = ledger if isinstance(ledger, Mapping) else {}
    root_state = identity.get("promotion_gate_state")
    root_evidence = identity.get("promotion_gate_evidence")
    root_decision = identity.get("promotion_decision")
    root_present = any(
        field_name in identity
        for field_name in (
            "promotion_gate_state",
            "promotion_gate_evidence",
            "promotion_decision",
        )
    )
    if root_present:
        if not (
            isinstance(root_state, Mapping)
            and isinstance(root_evidence, (list, tuple))
            and isinstance(root_decision, Mapping)
        ):
            raise ValueError("incomplete root promotion contract namespace")
        state, evidence, decision = root_state, root_evidence, root_decision
        ledger_state = ledger.get("promotion_gate_state")
        ledger_evidence = ledger.get("promotion_gate_evidence")
        ledger_decision = ledger.get("promotion_decision")
        ledger_present = any(
            field_name in ledger
            for field_name in (
                "promotion_gate_state",
                "promotion_gate_evidence",
                "promotion_decision",
            )
        )
        if ledger_present:
            if not (
                isinstance(ledger_state, Mapping)
                and isinstance(ledger_evidence, (list, tuple))
                and isinstance(ledger_decision, Mapping)
            ):
                raise ValueError("incomplete ledger promotion contract namespace")
            for field_name, root_value, ledger_value in (
                ("state", state, ledger_state),
                ("evidence", evidence, ledger_evidence),
                ("decision", decision, ledger_decision),
            ):
                if _canonical_hash(root_value) != _canonical_hash(ledger_value):
                    raise ValueError(f"root/ledger promotion {field_name} mismatch")
    else:
        state = ledger.get("promotion_gate_state")
        evidence = ledger.get("promotion_gate_evidence")
        decision = ledger.get("promotion_decision")
    if not isinstance(state, Mapping):
        raise ValueError("promotion_gate_state missing")
    if not isinstance(evidence, (list, tuple)):
        raise ValueError("promotion_gate_evidence missing")
    if not isinstance(decision, Mapping):
        raise ValueError("promotion_decision missing")
    return state, evidence, decision


def _legacy_generation_metadata(
    identity: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> tuple[str, Optional[int]]:
    root_present = any(
        field_name in identity
        for field_name in ("candidate_generation_status", "candidate_generation_cap")
    )
    ledger_present = any(
        field_name in ledger
        for field_name in ("candidate_generation_status", "candidate_generation_cap")
    )

    def _parse(container: Mapping[str, Any], label: str) -> tuple[str, Optional[int]]:
        status = str(container.get("candidate_generation_status") or "UNKNOWN").strip().upper()
        if status not in {"COMPLETE", "TRUNCATED", "UNKNOWN"}:
            raise ValueError(f"unsupported {label} candidate_generation_status")
        cap_value = container.get("candidate_generation_cap")
        cap: Optional[int] = None
        if cap_value is not None:
            cap = _strict_nonnegative_int(cap_value, f"{label} candidate_generation_cap")
            if cap <= 0:
                raise ValueError(f"{label} candidate_generation_cap must be positive")
        return status, cap

    root_value = _parse(identity, "root") if root_present else None
    ledger_value = _parse(ledger, "ledger") if ledger_present else None
    if root_value is not None and ledger_value is not None and root_value != ledger_value:
        raise ValueError("root/ledger candidate generation metadata mismatch")
    if ledger_value is not None:
        return ledger_value
    if root_value is not None:
        return root_value
    return "UNKNOWN", None


def _candidate_generation_metadata(
    identity: Mapping[str, Any],
) -> tuple[str, Optional[int]]:
    ledger = identity.get("candidate_ledger")
    ledger = ledger if isinstance(ledger, Mapping) else {}
    root_nested_present = "candidate_generation" in identity
    root_flat_present = any(
        field_name in identity
        for field_name in ("candidate_generation_status", "candidate_generation_cap")
    )
    ledger_nested_present = "candidate_generation" in ledger
    ledger_flat_present = any(
        field_name in ledger
        for field_name in ("candidate_generation_status", "candidate_generation_cap")
    )
    if root_nested_present:
        raise ValueError("root candidate generation metadata is forbidden")
    if any(
        field_name in identity
        for field_name in (
            "candidate_generation_proof",
            "candidate_producer_plans",
            "candidate_producer_receipts",
        )
    ):
        raise ValueError("root candidate producer proof metadata is forbidden")
    local_snapshot = None
    if ledger_nested_present:
        if root_flat_present:
            raise ValueError("root candidate generation metadata is forbidden")
        if ledger_flat_present:
            raise ValueError("mixed nested/flat ledger candidate generation metadata")
        retained_sources = identity.get("candidate_preservation_sources")
        if retained_sources is None:
            retained_sources = []
        local_snapshot = candidate_generation_snapshot_from_dict(
            ledger.get("candidate_generation"),
            retained_sources=_strict_sequence(
                retained_sources,
                "candidate_preservation_sources",
            ),
        )
        if local_snapshot.schema_version != CANDIDATE_GENERATION_VERSION:
            raise ValueError("candidate_generation must use candidate_generation_v1")
        local_status, local_cap = local_snapshot.status, local_snapshot.cap
    else:
        local_status, local_cap = _legacy_generation_metadata(identity, ledger)

    title_root_present = any(
        field_name in identity
        for field_name in (
            "title_candidate_generation",
            "title_candidate_generation_retained_sources",
        )
    )
    if title_root_present:
        raise ValueError("root title candidate generation metadata is forbidden")
    title_snapshot_present = "title_candidate_generation" in ledger
    title_sources_present = "title_candidate_generation_retained_sources" in ledger
    if title_snapshot_present != title_sources_present:
        raise ValueError("title candidate generation snapshot/source pair is incomplete")

    title_status = "UNKNOWN"
    title_cap: Optional[int] = None
    title_snapshot = None
    if title_snapshot_present:
        title_sources = _strict_sequence(
            ledger.get("title_candidate_generation_retained_sources"),
            "title_candidate_generation_retained_sources",
        )
        title_snapshot = candidate_generation_snapshot_from_dict(
            ledger.get("title_candidate_generation"),
            retained_sources=title_sources,
        )
        if title_snapshot.schema_version != TITLE_CANDIDATE_GENERATION_VERSION:
            raise ValueError(
                "title_candidate_generation must use title_candidate_generation_v1"
            )
        title_status, title_cap = title_snapshot.status, title_snapshot.cap

    truncated_caps = [
        cap
        for status, cap in (
            (local_status, local_cap),
            (title_status, title_cap),
        )
        if status == "TRUNCATED" and cap is not None
    ]
    if truncated_caps:
        return "TRUNCATED", min(truncated_caps)
    proof_present = "candidate_generation_proof" in ledger
    plans_present = "candidate_producer_plans" in ledger
    receipts_present = "candidate_producer_receipts" in ledger
    if proof_present or plans_present or receipts_present:
        if not (proof_present and plans_present and receipts_present):
            raise ValueError("candidate producer proof/plan/receipt set is incomplete")
        if local_snapshot is None or title_snapshot is None:
            raise ValueError("candidate producer proof requires both local snapshots")
        producer_plans = candidate_producer_plans_from_payload(
            _strict_sequence(
                ledger.get("candidate_producer_plans"),
                "candidate_producer_plans",
            )
        )
        producer_receipts = candidate_producer_receipts_from_payload(
            _strict_sequence(
                ledger.get("candidate_producer_receipts"),
                "candidate_producer_receipts",
            )
        )
        stored_proof = candidate_generation_proof_from_dict(
            ledger.get("candidate_generation_proof")
        )
        recomputed_proof = build_candidate_generation_proof(
            producer_plans,
            producer_receipts,
            local_snapshots=(local_snapshot, title_snapshot),
            required_producers=("search", "fetch"),
        )
        if stored_proof.to_ledger_dict() != recomputed_proof.to_ledger_dict():
            raise ValueError("candidate generation proof does not bind plan/receipt set")
        if stored_proof.status == "COMPLETE":
            return "COMPLETE", None
    # Producer proof가 없거나 UNKNOWN/TRUNCATED이면 recall 계산을 열지 않는다.
    # Producer-level loss는 하나의 CandidateSet cap으로 환산할 수 없으므로
    # local cap TRUNCATED가 아닌 경우 CandidateSet 상태는 UNKNOWN으로 남긴다.
    return "UNKNOWN", title_cap if title_snapshot_present else local_cap


def selective_shadow_from_identity(identity: Mapping[str, Any]) -> SelectiveShadowDecision:
    if not isinstance(identity, Mapping):
        raise ValueError("identity must be a mapping")
    state_payload, evidence_payload, stored_decision = _identity_contract_payloads(identity)
    state = grounding_state_from_dict(state_payload)
    evidence = evidence_records_from_payload(evidence_payload)
    replay = can_publish_title(state, evidence)
    if _canonical_hash(stored_decision) != _canonical_hash(replay.to_dict()):
        raise ValueError("stored promotion decision does not replay exactly")
    additional_sources = [
        (field_name, identity.get(field_name))
        for field_name in _CANDIDATE_SOURCE_FIELDS
        if identity.get(field_name) not in (None, "")
    ]
    generation_status, generation_cap = _candidate_generation_metadata(identity)
    return build_uncalibrated_selective_shadow(
        state,
        evidence,
        replay,
        additional_sources=additional_sources,
        generation_status=generation_status,
        generation_cap=generation_cap,
    )


def candidate_option_from_dict(value: Any) -> CandidateOption:
    if not isinstance(value, Mapping):
        raise ValueError("candidate option must be an object")
    return CandidateOption(
        candidate_id=str(value.get("candidate_id") or ""),
        titles=_dedupe_sorted(_strict_sequence(value.get("titles"), "titles")),
        urls=_dedupe_sorted(_strict_sequence(value.get("urls"), "urls")),
        aliases=_dedupe_sorted(_strict_sequence(value.get("aliases"), "aliases")),
        option_kind=str(value.get("option_kind") or ""),
        event_eligible=_strict_bool(value.get("event_eligible"), "event_eligible"),
        source_fields=_dedupe_sorted(
            _strict_sequence(value.get("source_fields"), "source_fields")
        ),
        evidence_kinds=_dedupe_sorted(
            _strict_sequence(value.get("evidence_kinds"), "evidence_kinds")
        ),
        source_tiers=_dedupe_sorted(
            _strict_sequence(value.get("source_tiers"), "source_tiers")
        ),
        reference_roles=_dedupe_sorted(
            _strict_sequence(value.get("reference_roles"), "reference_roles")
        ),
        preservation_roles=_dedupe_sorted(
            _strict_sequence(value.get("preservation_roles"), "preservation_roles")
        ),
        promotion_policies=_dedupe_sorted(
            _strict_sequence(value.get("promotion_policies"), "promotion_policies")
        ),
        local_preservation_types=_dedupe_sorted(
            _strict_sequence(value.get("local_preservation_types"), "local_preservation_types")
        ),
        reason_codes=_dedupe_sorted(
            _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        negative_evidence=_dedupe_sorted(
            _strict_sequence(value.get("negative_evidence"), "negative_evidence")
        ),
        baseline_selected=_strict_bool(value.get("baseline_selected"), "baseline_selected"),
        publish_support_present=_strict_bool(
            value.get("publish_support_present"), "publish_support_present"
        ),
        identity_conflict=_strict_bool(value.get("identity_conflict"), "identity_conflict"),
    )


def candidate_set_from_dict(value: Any) -> CandidateSet:
    if not isinstance(value, Mapping):
        raise ValueError("candidate set must be an object")
    candidates = tuple(
        candidate_option_from_dict(item)
        for item in _strict_sequence(value.get("candidates"), "candidates")
    )
    result = CandidateSet(
        candidates=candidates,
        source_record_count=_strict_nonnegative_int(
            value.get("source_record_count"), "source_record_count"
        ),
        source_candidate_pair_count=_strict_nonnegative_int(
            value.get("source_candidate_pair_count"), "source_candidate_pair_count"
        ),
        typed_inventory_pair_count=_strict_nonnegative_int(
            value.get("typed_inventory_pair_count"), "typed_inventory_pair_count"
        ),
        candidate_inventory_count_hint=_strict_nonnegative_int(
            value.get("candidate_inventory_count_hint"), "candidate_inventory_count_hint"
        ),
        work_candidate_count=_strict_nonnegative_int(
            value.get("work_candidate_count"), "work_candidate_count"
        ),
        unlinked_surface_count=_strict_nonnegative_int(
            value.get("unlinked_surface_count"), "unlinked_surface_count"
        ),
        observed_late_surface_count=_strict_nonnegative_int(
            value.get("observed_late_surface_count"), "observed_late_surface_count"
        ),
        event_candidate_count=_strict_nonnegative_int(
            value.get("event_candidate_count"), "event_candidate_count"
        ),
        generation_status=str(value.get("generation_status") or ""),
        generation_cap=(
            _strict_nonnegative_int(value.get("generation_cap"), "generation_cap")
            if value.get("generation_cap") is not None
            else None
        ),
        candidate_set_recall_status=str(value.get("candidate_set_recall_status") or ""),
        observation_signatures=tuple(
            str(item or "").strip().lower()
            for item in _strict_sequence(
                value.get("observation_signatures"), "observation_signatures"
            )
        ),
        integrity_status=str(value.get("integrity_status") or ""),
        reason_codes=_dedupe_sorted(
            _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        candidate_set_fingerprint=_require_sha256(
            value.get("candidate_set_fingerprint"), "candidate_set_fingerprint"
        ),
        observation_fingerprint=_require_sha256(
            value.get("observation_fingerprint"), "observation_fingerprint"
        ),
        nil_label=str(value.get("nil_label") or ""),
        schema_version=str(value.get("schema_version") or ""),
    )
    if _canonical_hash(result.identity_payload()) != result.candidate_set_fingerprint:
        raise ValueError("candidate_set_fingerprint mismatch")
    if (
        _canonical_hash(result.observation_payload_without_fingerprints())
        != result.observation_fingerprint
    ):
        raise ValueError("observation_fingerprint mismatch")
    return result


def selective_shadow_from_dict(value: Any) -> SelectiveShadowDecision:
    if not isinstance(value, Mapping):
        raise ValueError("selective shadow must be an object")
    candidate_set = candidate_set_from_dict(value.get("candidate_set"))
    probabilities = tuple(
        LabelProbability(
            label=str(item.get("label") or "") if isinstance(item, Mapping) else "",
            probability=item.get("probability") if isinstance(item, Mapping) else None,
        )
        for item in _strict_sequence(value.get("event_probabilities"), "event_probabilities")
    )
    result = SelectiveShadowDecision(
        candidate_set=candidate_set,
        event_probabilities=probabilities,
        probability_status=str(value.get("probability_status") or ""),
        selected_label=(
            str(value.get("selected_label"))
            if value.get("selected_label") not in (None, "")
            else None
        ),
        action=str(value.get("action") or ""),
        action_applied=_strict_bool(value.get("action_applied"), "action_applied"),
        operational_effect=str(value.get("operational_effect") or ""),
        reason_codes=_dedupe_sorted(
            _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        baseline_decision_fingerprint=_require_sha256(
            value.get("baseline_decision_fingerprint"), "baseline_decision_fingerprint"
        ),
        baseline_selected_candidate_id=(
            str(value.get("baseline_selected_candidate_id"))
            if value.get("baseline_selected_candidate_id") not in (None, "")
            else None
        ),
        input_fingerprint=_require_sha256(value.get("input_fingerprint"), "input_fingerprint"),
        shadow_fingerprint=_require_sha256(value.get("shadow_fingerprint"), "shadow_fingerprint"),
        schema_version=str(value.get("schema_version") or ""),
    )
    if _canonical_hash(result.payload_without_shadow_fingerprint()) != result.shadow_fingerprint:
        raise ValueError("shadow_fingerprint mismatch")
    return result


def unavailable_shadow_payload(reason_code: str) -> dict[str, Any]:
    """Return a non-authoritative fail-closed diagnostic for runtime attachment."""

    return {
        "schema_version": SELECTIVE_SHADOW_UNAVAILABLE_VERSION,
        "probability_status": "NOT_AVAILABLE_TYPED_CONTRACT_INVALID",
        "selected_label": None,
        "action": SHADOW_ACTION_ABSTAIN,
        "action_applied": False,
        "operational_effect": SHADOW_OPERATIONAL_EFFECT,
        "reason_codes": [str(reason_code or "typed_publish_contract_invalid")],
    }
