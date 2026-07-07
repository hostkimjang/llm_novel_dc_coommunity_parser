"""Shared title-promotion gate contracts.

This module keeps the publish decision separate from source existence. A title
can be a real official work and still be unsafe to publish for a specific post
when the post does not discuss that work as work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


BLOCKING_REASON_CODES = {
    "community_banter",
    "context_only",
    "nonwork",
    "thematic_overlap_only",
    "row_discussion_missing",
    "variance_quarantine",
    "same_title_source_movement",
    "caveated_alias_boundary",
}

CURRENT_WORK_REASON_MARKERS = {
    "scope_current_work",
    "row_discusses_work_as_work",
}
NONCURRENT_SCOPE_REASON_MARKERS = {
    "context_only",
    "scope_context_only",
    "scope_not_current_work",
    "scope_unknown",
    "scope_unclassified",
    "row_discussion_missing",
    "nonwork",
    "nonwork_or_noise_context",
    "community_banter",
    "scope_platform_meta_nonwork",
    "non_novel_discourse",
}

HARD_BLOCKING_REASON_CODES = {
    "thematic_overlap_only",
}

SCOPE_CURRENT_WORK = "current_work"
SCOPE_KINDS = {
    SCOPE_CURRENT_WORK,
    "previous_work",
    "secondary_reference",
    "author_new_work",
    "image_ocr_derived_work",
    "platform_meta_nonwork",
    "context_only",
    "unknown",
}


@dataclass(frozen=True)
class EvidenceRecord:
    kind: str
    strength: str = "medium"
    source_path_or_snippet: str = ""
    supports_publish: bool = False
    reason_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScopeState:
    scope_kind: str = "unknown"
    confidence: str = "medium"
    direct_bridge_sources: List[str] = field(default_factory=list)
    competing_candidates: List[str] = field(default_factory=list)
    conflict_reason_codes: List[str] = field(default_factory=list)

    def normalized_kind(self) -> str:
        kind = str(self.scope_kind or "").strip().lower()
        return kind if kind in SCOPE_KINDS else "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroundingState:
    post_id: Optional[int]
    candidate_title: str
    candidate_url: str = ""
    source: str = "title_promotion"
    official_title_exists: bool = False
    row_discusses_work_as_work: bool = False
    title_resolution_state: str = ""
    work_resolution: str = ""
    discussion_type: str = ""
    prior_variance_quarantine: bool = False
    same_title_source_movement: bool = False
    caveated_alias_boundary: bool = False
    scope: Optional[ScopeState] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PromotionDecision:
    status: str
    publish_allowed: bool
    official_title: Optional[str] = None
    official_url: Optional[str] = None
    candidate_preserved: bool = False
    reason_codes: List[str] = field(default_factory=list)
    bypassed_gate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GateReport:
    run_integrity: str = "UNKNOWN"
    targeted_canary_status: str = "UNKNOWN"
    semantic_quality: str = "REVIEW-LOCKED"
    full_scan_approval: bool = False
    collateral_regression_count: Optional[int] = None
    golden_gate: str = "UNKNOWN"
    next_actionable_queue: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _dedupe(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def normalize_scope_reason_codes(
    reason_codes: Iterable[str],
    *,
    scope_kind: str = "",
) -> List[str]:
    """Remove stale current/non-current scope reason mixtures."""
    codes = _dedupe(reason_codes)
    code_set = set(codes)
    normalized_scope = str(scope_kind or "").strip().lower()
    current_markers = code_set & CURRENT_WORK_REASON_MARKERS
    noncurrent_markers = code_set & NONCURRENT_SCOPE_REASON_MARKERS

    if normalized_scope == SCOPE_CURRENT_WORK or (
        current_markers and not code_set.intersection({"scope_not_current_work", "scope_context_only"})
    ):
        return [code for code in codes if code not in NONCURRENT_SCOPE_REASON_MARKERS]
    if normalized_scope and normalized_scope != SCOPE_CURRENT_WORK and current_markers and noncurrent_markers:
        cleaned: List[str] = []
        discussion_marker_added = False
        for code in codes:
            if code == "row_discusses_work_as_work":
                if not discussion_marker_added:
                    cleaned.append("row_discussion_present_noncurrent_scope")
                    discussion_marker_added = True
                continue
            if code == "scope_current_work":
                continue
            cleaned.append(code)
        return _dedupe(cleaned)
    return codes


def _state_reason_codes(state: GroundingState) -> List[str]:
    codes: List[str] = []
    scope_kind = state.scope.normalized_kind() if isinstance(state.scope, ScopeState) else ""
    scope_blocks_current_marker = bool(scope_kind and scope_kind != SCOPE_CURRENT_WORK)
    row_discusses_current_work = state.row_discusses_work_as_work and not scope_blocks_current_marker
    if state.official_title_exists:
        codes.append("official_title_exists")
    if row_discusses_current_work:
        codes.append("row_discusses_work_as_work")
    elif state.row_discusses_work_as_work:
        codes.append("row_discussion_present_noncurrent_scope")
    else:
        codes.append("row_discussion_missing")

    resolution_state = str(state.title_resolution_state or "").strip().lower()
    if not row_discusses_current_work and resolution_state in {"context_only", "nonwork"}:
        codes.append(resolution_state)

    work_resolution = str(state.work_resolution or "").strip().lower()
    if not row_discusses_current_work and work_resolution in {"context_only", "nonwork"}:
        codes.append(work_resolution)

    discussion_type = str(state.discussion_type or "").strip().lower()
    if not row_discusses_current_work and discussion_type == "community_banter":
        codes.append("community_banter")

    if state.prior_variance_quarantine:
        codes.append("variance_quarantine")
    if state.same_title_source_movement:
        codes.append("same_title_source_movement")
    if state.caveated_alias_boundary:
        codes.append("caveated_alias_boundary")
    if isinstance(state.scope, ScopeState):
        codes.append(f"scope_{scope_kind}")
        if scope_kind != SCOPE_CURRENT_WORK:
            codes.append("scope_not_current_work")
        codes.extend(state.scope.conflict_reason_codes)
    return normalize_scope_reason_codes(codes, scope_kind=scope_kind)


def can_publish_title(
    state: GroundingState,
    evidence: Optional[Iterable[EvidenceRecord]] = None,
) -> PromotionDecision:
    """Return a contract-testable public title promotion decision."""
    records = [record for record in (evidence or []) if isinstance(record, EvidenceRecord)]
    evidence_codes = [
        record.reason_code
        for record in records
        if str(record.reason_code or "").strip()
    ]
    reason_codes = _dedupe([*_state_reason_codes(state), *evidence_codes])

    candidate_title = str(state.candidate_title or "").strip()
    candidate_url = str(state.candidate_url or "").strip()
    if not candidate_title:
        return PromotionDecision(
            status="reject",
            publish_allowed=False,
            official_title=None,
            official_url=None,
            candidate_preserved=False,
            reason_codes=_dedupe(["no_candidate_title", *reason_codes]),
            bypassed_gate=False,
        )

    supports_publish = any(record.supports_publish for record in records)
    blocking_reasons = BLOCKING_REASON_CODES.intersection(reason_codes)
    hard_blocking_reasons = HARD_BLOCKING_REASON_CODES.intersection(reason_codes)
    scope_kind = state.scope.normalized_kind() if isinstance(state.scope, ScopeState) else ""
    scope_blocks_publish = bool(scope_kind and scope_kind != SCOPE_CURRENT_WORK)
    if state.prior_variance_quarantine or state.same_title_source_movement:
        status = "quarantine"
    elif scope_blocks_publish:
        status = "candidate_only"
    elif hard_blocking_reasons and not state.row_discusses_work_as_work:
        status = "candidate_only"
    elif state.row_discusses_work_as_work and (state.official_title_exists or supports_publish):
        status = "publish"
    elif state.caveated_alias_boundary and not state.row_discusses_work_as_work:
        status = "candidate_only"
    elif blocking_reasons:
        status = "candidate_only"
    elif state.row_discusses_work_as_work:
        status = "hold"
    else:
        status = "candidate_only"

    publish_allowed = status == "publish"
    return PromotionDecision(
        status=status,
        publish_allowed=publish_allowed,
        official_title=candidate_title if publish_allowed else None,
        official_url=candidate_url if publish_allowed and candidate_url else None,
        candidate_preserved=not publish_allowed,
        reason_codes=reason_codes,
        bypassed_gate=False,
    )
