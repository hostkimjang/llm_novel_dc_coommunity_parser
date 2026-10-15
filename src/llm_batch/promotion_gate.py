"""공개 제목과 URL의 최종 승격을 단일화하는 공통 계약.

공식 작품이 실제로 존재한다는 사실과 현재 게시글에 공개해도 안전하다는 판단은
서로 다르다. 후보가 실재하더라도 게시글이 그 작품을 작품으로 다루지 않으면
candidate-only로 보존하고 공개 필드는 fail-close한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from functools import lru_cache
import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from .record_role_types import RecordRoleProvenanceDraft
from .record_role_transport import RolePass, prepare_pass, observe_consumed, bind_return


PUBLISH_CONTRACT_VERSION = "promotion_contract_v2"
TRACKING_QUERY_KEYS = {
    "campaign",
    "fbclid",
    "from",
    "gclid",
    "ref",
    "sid",
    "source",
}


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

CONTRACT_BLOCKING_REASON_CODES = {
    "search_blind_condition",
    "search_evidence_missing",
    "canonical_variant_policy_pending",
    "stronger_evidence_required",
    "serializer_candidate_removed",
    "post_gate_candidate_mismatch",
    "post_serializer_contract_mismatch",
    "official_title_looks_like_url_or_domain",
    "official_title_looks_like_generic_non_title_surface",
    "official_title_looks_like_generic_evidence_label",
    "official_title_looks_like_search_snippet",
    "official_title_looks_like_breadcrumb",
    "official_title_looks_like_listing_description",
    "official_detail_display_title_mismatch",
    "title_body_subject_conflict_unresolved",
    "title_resolution_state_not_publishable",
    "work_resolution_not_publishable",
    "evidence_conflict",
    "evidence_insufficient",
    "evidence_status_not_publishable",
    "non_novel_media",
    "cross_media_unresolved",
    "media_domain_not_novel_work",
    "multiple_primary_works",
    "no_unique_primary_work",
    "primary_work_ambiguous",
    "primary_work_status_not_publishable",
    "unverified_edition_title_only",
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

SEMANTIC_EVIDENCE_SUFFICIENT = "sufficient"
SEMANTIC_MEDIA_NOVEL_WORK = "novel_work"
SEMANTIC_PRIMARY_UNIQUE = "unique"


@dataclass(frozen=True)
class EvidenceRecord:
    kind: str
    strength: str = "medium"
    source_path_or_snippet: str = ""
    supports_publish: bool = False
    reason_code: str = ""
    candidate_title: str = ""
    candidate_url: str = ""
    title_url_match: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScopeState:
    scope_kind: str = "unknown"
    confidence: str = "medium"
    direct_bridge_sources: Tuple[str, ...] = field(default_factory=tuple)
    competing_candidates: Tuple[str, ...] = field(default_factory=tuple)
    conflict_reason_codes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "direct_bridge_sources", tuple(self.direct_bridge_sources))
        object.__setattr__(self, "competing_candidates", tuple(self.competing_candidates))
        object.__setattr__(self, "conflict_reason_codes", tuple(self.conflict_reason_codes))

    def normalized_kind(self) -> str:
        kind = str(self.scope_kind or "").strip().lower()
        return kind if kind in SCOPE_KINDS else "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_kind": self.scope_kind,
            "confidence": self.confidence,
            "direct_bridge_sources": list(self.direct_bridge_sources),
            "competing_candidates": list(self.competing_candidates),
            "conflict_reason_codes": list(self.conflict_reason_codes),
        }


@dataclass(frozen=True)
class SemanticPublicationState:
    """Typed semantic authority for the final public projection.

    Empty fields are a legacy-compatible no-op.  Once an upstream producer
    explicitly supplies a field, only the publishable value is allow-listed;
    conflict/insufficient, non-novel/cross-media, and non-unique primary-work
    states therefore fail closed even if a later stage tries to revive a title.
    """

    evidence_status: str = ""
    media_domain_class: str = ""
    primary_work_status: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_status",
            "media_domain_class",
            "primary_work_status",
        ):
            if not isinstance(getattr(self, field_name), str):
                raise ValueError(f"semantic_publication.{field_name} must be a string")

    def normalized_evidence_status(self) -> str:
        return str(self.evidence_status or "").strip().lower()

    def normalized_media_domain_class(self) -> str:
        return str(self.media_domain_class or "").strip().lower()

    def normalized_primary_work_status(self) -> str:
        return str(self.primary_work_status or "").strip().lower()

    def is_default(self) -> bool:
        return not (
            self.normalized_evidence_status()
            or self.normalized_media_domain_class()
            or self.normalized_primary_work_status()
        )

    def derived_reason_codes(self) -> List[str]:
        codes: List[str] = []
        evidence_status = self.normalized_evidence_status()
        media_domain = self.normalized_media_domain_class()
        primary_status = self.normalized_primary_work_status()

        if evidence_status and evidence_status != SEMANTIC_EVIDENCE_SUFFICIENT:
            codes.append(
                "evidence_conflict"
                if evidence_status == "conflict"
                else "evidence_insufficient"
                if evidence_status == "insufficient"
                else "evidence_status_not_publishable"
            )
        if media_domain and media_domain != SEMANTIC_MEDIA_NOVEL_WORK:
            codes.append(
                "non_novel_media"
                if media_domain == "non_novel_media"
                else "cross_media_unresolved"
                if media_domain == "cross_media_unresolved"
                else "media_domain_not_novel_work"
            )
        if primary_status and primary_status != SEMANTIC_PRIMARY_UNIQUE:
            codes.append(
                "multiple_primary_works"
                if primary_status in {"multiple", "multiwork"}
                else "no_unique_primary_work"
                if primary_status in {"missing", "none", "no_unique"}
                else "primary_work_ambiguous"
                if primary_status == "ambiguous"
                else "primary_work_status_not_publishable"
            )
        return _dedupe(codes)

    def blocks_publish(self) -> bool:
        return bool(self.derived_reason_codes())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_status": self.evidence_status,
            "media_domain_class": self.media_domain_class,
            "primary_work_status": self.primary_work_status,
        }


@dataclass(frozen=True)
class EditionCurrentRelation:
    """Post-source authority for one candidate's selected edition."""

    candidate_title: str
    markers: Tuple[str, ...]
    status: str  # affirmed, denied, other_actor, reported, pending, unresolved
    basis: str
    source_role: str
    source_index: int
    evidence_span: Tuple[int, int]
    native_reduction: Mapping[str, Any] = field(default_factory=dict, compare=False)
    record_role_provenance: Tuple[RecordRoleProvenanceDraft, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_title, str) or not self.candidate_title.strip():
            raise ValueError("edition current relation requires candidate_title")
        if self.status not in {"affirmed", "denied", "other_actor", "reported", "pending", "unresolved"}:
            raise ValueError("edition current relation status is invalid")
        if self.status == "affirmed" and self.basis not in {
            "author_read", "author_identify", "current_post_record", "bound_comment_identify",
        }:
            raise ValueError("affirmed edition relation requires an author-bound basis")
        if self.source_role not in {"post_title", "post_body", "comment", "unknown"}:
            raise ValueError("edition current relation source_role is invalid")
        if not isinstance(self.source_index, int) or self.source_index < 0:
            raise ValueError("edition current relation source_index is invalid")
        if (not isinstance(self.evidence_span, tuple) or len(self.evidence_span) != 2
                or any(not isinstance(pos, int) or pos < 0 for pos in self.evidence_span)
                or self.evidence_span[1] < self.evidence_span[0]):
            raise ValueError("edition current relation evidence_span is invalid")
        if not isinstance(self.markers, tuple) or not self.markers or any(
            not isinstance(marker, str) or not marker for marker in self.markers
        ):
            raise ValueError("edition current relation markers are invalid")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_title": self.candidate_title,
            "markers": list(self.markers),
            "status": self.status,
            "basis": self.basis,
            "source_role": self.source_role,
            "source_index": self.source_index,
            "evidence_span": list(self.evidence_span),
        }


@dataclass(frozen=True)
class EditionPublicationState:
    """Post-side edition mention and competing search variants for title promotion.

    ``source_checked`` distinguishes an inspected post with no edition marker
    from a legacy caller that did not supply post-side evidence. Search result
    titles must never be copied into ``explicit_edition_markers``.
    """

    source_checked: bool = False
    explicit_edition_markers: Tuple[str, ...] = field(default_factory=tuple)
    competing_variant_titles: Tuple[str, ...] = field(default_factory=tuple)
    current_relation: Optional[EditionCurrentRelation] = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_checked, bool):
            raise ValueError("edition_publication.source_checked must be a bool")
        object.__setattr__(self, "explicit_edition_markers", tuple(self.explicit_edition_markers))
        object.__setattr__(self, "competing_variant_titles", tuple(self.competing_variant_titles))
        if self.current_relation is not None and not isinstance(self.current_relation, EditionCurrentRelation):
            raise ValueError("edition_publication.current_relation must be typed")

    def is_default(self) -> bool:
        return not (
            self.source_checked
            or self.explicit_edition_markers
            or self.competing_variant_titles
            or self.current_relation is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_checked": self.source_checked,
            "explicit_edition_markers": list(self.explicit_edition_markers),
            "competing_variant_titles": list(self.competing_variant_titles),
            "current_relation": self.current_relation.to_dict() if self.current_relation else None,
        }


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
    candidate_inventory_count: int = 0
    scope: Optional[ScopeState] = None
    retrieval: Optional["RetrievalState"] = None
    semantic_publication: Optional[SemanticPublicationState] = None
    edition_publication: Optional[EditionPublicationState] = None

    def __post_init__(self) -> None:
        value = self.candidate_inventory_count
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("candidate_inventory_count must be a nonnegative int")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        # Keep existing v2 fingerprints stable for the overwhelmingly common
        # no-inventory case.  A non-zero inventory is an authoritative typed
        # input and is therefore intentionally fingerprinted.
        if not self.candidate_inventory_count:
            payload.pop("candidate_inventory_count", None)
        # Keep existing v2 fingerprints stable for the overwhelmingly common
        # no-retrieval case.  A populated RetrievalState is an authoritative
        # typed input and is therefore intentionally fingerprinted.
        if not isinstance(self.retrieval, RetrievalState) or self.retrieval.is_default():
            payload.pop("retrieval", None)
        else:
            payload["retrieval"] = self.retrieval.to_dict()
        # Preserve v2 fingerprints for legacy/default callers.  A populated
        # semantic authority is part of the sealed decision input.
        if (
            not isinstance(self.semantic_publication, SemanticPublicationState)
            or self.semantic_publication.is_default()
        ):
            payload.pop("semantic_publication", None)
        else:
            payload["semantic_publication"] = self.semantic_publication.to_dict()
        if (
            not isinstance(self.edition_publication, EditionPublicationState)
            or self.edition_publication.is_default()
        ):
            payload.pop("edition_publication", None)
        else:
            payload["edition_publication"] = self.edition_publication.to_dict()
        payload["scope"] = self.scope.to_dict() if isinstance(self.scope, ScopeState) else None
        return payload


@dataclass(frozen=True)
class RetrievalState:
    """Typed per-row search/retrieval outcome consumed by the publish gate.

    The publish decision must not depend on whether an upstream stage happened
    to emit a free-form ``search_evidence_missing`` reason code.  When a row
    requires external-source grounding to publish a public title and that
    grounding was attempted but not recovered (or the search stage was hard
    blocked), the gate must fail-close on typed evidence alone.

    All fields default to a no-op so existing callers and fingerprints are
    unchanged.  Only a populated (non-default) ``RetrievalState`` is treated as
    an authoritative typed input and is therefore fingerprinted.
    """

    required: bool = False
    attempted: bool = False
    recovered: bool = False
    hard_blocked: bool = False
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name in ("required", "attempted", "recovered", "hard_blocked"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a bool")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))

    def is_default(self) -> bool:
        return not (
            self.required
            or self.attempted
            or self.recovered
            or self.hard_blocked
            or self.reason_codes
        )

    def blocks_publish(self) -> bool:
        """True when required grounding was not recovered or was hard blocked."""
        if self.hard_blocked:
            return True
        return bool(self.required and not self.recovered)

    def derived_reason_codes(self) -> List[str]:
        codes: List[str] = []
        if self.hard_blocked:
            codes.append("search_blind_condition")
        if self.required and not self.recovered:
            codes.append("search_evidence_missing")
        codes.extend(str(code or "").strip() for code in self.reason_codes)
        return _dedupe(codes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required": self.required,
            "attempted": self.attempted,
            "recovered": self.recovered,
            "hard_blocked": self.hard_blocked,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class PromotionDecision:
    status: str
    publish_allowed: bool
    official_title: Optional[str] = None
    official_url: Optional[str] = None
    candidate_preserved: bool = False
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    bypassed_gate: bool = False
    scope: Optional[ScopeState] = None
    input_fingerprint: str = ""
    contract_version: str = PUBLISH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["reason_codes"] = list(self.reason_codes)
        payload["scope"] = self.scope.to_dict() if isinstance(self.scope, ScopeState) else None
        return payload


@dataclass(frozen=True)
class PublishIdentity:
    official_title: Optional[str] = None
    official_url: Optional[str] = None
    title_resolution_allowed: Optional[bool] = None
    title_resolution_state: Optional[str] = None
    work_resolution: Optional[str] = None
    candidate_ledger_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublishContractTrace:
    pre_gate_candidate: PublishIdentity
    gate_decision: PromotionDecision
    scope_state: Optional[ScopeState]
    post_gate_identity: PublishIdentity
    reason_codes: Tuple[str, ...]
    input_fingerprint: str
    contract_version: str = PUBLISH_CONTRACT_VERSION
    bypassed_gate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pre_gate_candidate": self.pre_gate_candidate.to_dict(),
            "gate_decision": self.gate_decision.to_dict(),
            "scope_state": (
                self.scope_state.to_dict()
                if isinstance(self.scope_state, ScopeState)
                else None
            ),
            "post_gate_identity": self.post_gate_identity.to_dict(),
            "reason_codes": list(self.reason_codes),
            "input_fingerprint": self.input_fingerprint,
            "contract_version": self.contract_version,
            "bypassed_gate": self.bypassed_gate,
        }


@dataclass(frozen=True)
class PublishContract:
    state: GroundingState
    evidence: Tuple[EvidenceRecord, ...]
    decision: PromotionDecision
    trace: PublishContractTrace
    input_fingerprint: str
    contract_version: str = PUBLISH_CONTRACT_VERSION
    native_input_trace: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "input_fingerprint": self.input_fingerprint,
            "state": self.state.to_dict(),
            "evidence": [record.to_dict() for record in self.evidence],
            "decision": self.decision.to_dict(),
            "trace": self.trace.to_dict(),
        }


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


def _nonnegative_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("candidate_inventory_count must be a nonnegative int")
    return value


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
    # Empty legacy state remains backward-compatible, but an explicit state is
    # authoritative: only resolved/direct_resolved may reach the public title
    # surface.  This deliberately fail-closes future HOLD-like enum additions
    # instead of requiring every new non-publishable state to be blocklisted.
    if resolution_state and resolution_state not in {"resolved", "direct_resolved"}:
        codes.append("title_resolution_state_not_publishable")
    if not row_discusses_current_work and resolution_state in {"context_only", "nonwork"}:
        codes.append(resolution_state)

    work_resolution = str(state.work_resolution or "").strip().lower()
    if work_resolution and work_resolution != "resolved":
        codes.append("work_resolution_not_publishable")
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
    else:
        codes.extend(["scope_unknown", "scope_not_current_work", "fail_closed_scope_missing"])
    if isinstance(state.retrieval, RetrievalState) and state.retrieval.blocks_publish():
        codes.extend(state.retrieval.derived_reason_codes())
    if (
        isinstance(state.semantic_publication, SemanticPublicationState)
        and state.semantic_publication.blocks_publish()
    ):
        codes.extend(state.semantic_publication.derived_reason_codes())
    return normalize_scope_reason_codes(codes, scope_kind=scope_kind)


def _canonical_payload(value: Any) -> Any:
    if isinstance(
        value,
        (
            EvidenceRecord,
            ScopeState,
            SemanticPublicationState,
            EditionPublicationState,
            GroundingState,
            RetrievalState,
            PromotionDecision,
        ),
    ):
        return _canonical_payload(value.to_dict())
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_payload(item) for item in value]
    return value


def publish_input_fingerprint(
    state: GroundingState,
    evidence: Iterable[EvidenceRecord],
) -> str:
    payload = {
        "contract_version": PUBLISH_CONTRACT_VERSION,
        "state": _canonical_payload(state),
        "evidence": _canonical_payload(list(evidence)),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _title_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


_EDITION_MARKER_RE = re.compile(
    r"[\[\(]\s*(단행본|연재본|연재|개정판|합본|특별판|완전판|전자책|이북|ebook|e북|e)\s*[\]\)]",
    flags=re.IGNORECASE,
)

_EDITION_DENIAL_RE = re.compile(
    r"^\s*(?:[이가은는]?\s*(?:아니라|아니고|아닌|아님|아니다|아니야|아니에요|아니지)|"
    r"일\s*리\s*없|말고|제외|이?라기보다)"
)
_REPORTED_DENIAL_RE = re.compile(
    r"(?:했지만|했는데|했다지만|라지만|이라지만).{0,24}(?:아닌|아니|아님|틀린|잘못|반박)"
)
_REPORTED_CLAIM_RE = re.compile(r"^['\"”’`]?\s*(?:이라고|라고)\s*(?:했|말했|주장했)")
_DIRECT_EDITION_USE_RE = re.compile(r"(?:읽|재독|완독|봤|보는|보고|감상|얘기|추천|재밌|재미|좋)")
_EDITION_DISCOURSE_ADJUNCTS = frozenset({"정작", "실은", "사실은", "오히려", "반대로"})


def _edition_current_post_prefix(prefix: str) -> bool:
    """Bind a comment's relative clause to this post, not another owner's post."""
    match = re.search(
        r"(?:^|[\s'\"“‘`])(?:원글|본문|(?:이|그|해당)\s*"
        r"(?:글|게시글|게시물|포스트))(?:의|에서|에)\s*"
        r"(?P<relative>[가-힣]+)?\s*$",
        prefix,
    )
    if not match:
        return False
    relative = match.group("relative")
    if not relative:
        return True
    kiwi = _edition_kiwi()
    if kiwi is None:
        return False
    try:
        tokens = kiwi.tokenize(relative)
    except Exception:
        return False
    return bool(
        tokens and tokens[-1].tag == "ETM"
        and any(token.tag.startswith("VV") or token.tag == "XSV" for token in tokens[:-1])
    )


def _edition_current_book_target(prefix: str) -> bool:
    """A deictic book or one explicitly in the original post is the target."""
    match = re.search(
        r"(?:^|\s)(?:이\s+책|"
        r"(?:원글|본문|(?:이|그|해당)\s*글)"
        r"(?:에서\s*(?:읽은|말한|언급한)|의)\s*(?:그|이)?\s*책"
        r"(?:\s*판본)?)"
        r"[이가은는]\s*$", prefix,
    )
    return bool(match and _edition_subject_actor(prefix[:match.start()]) != "other")


def _edition_completed_identification(following: str) -> bool:
    """Classify a finished identification by the confirmer, not its source noun."""
    text = following.strip().rstrip(".!。 ")
    match = re.fullmatch(
        r"(?:이?라고|라고|임을)\s*(?P<scope>.{0,45}?)"
        r"(?:직접\s*)?(?:확인|검증)(?:했(?:습니다|어요|다)|함)", text,
    )
    if not match:
        return False
    return _edition_subject_actor(match.group("scope")) != "other"


def _edition_is_adverbial_modifier(surface: str) -> bool:
    kiwi = _edition_kiwi()
    if kiwi is None:
        return False
    try:
        tokens = kiwi.tokenize(surface)
    except Exception:
        return False
    return len(tokens) == 1 and tokens[0].tag in {"MAG", "MAJ"}


def _edition_discourse_connector(surface: str) -> bool:
    """A verb plus connective endings cannot extend a work title."""
    kiwi = _edition_kiwi()
    if kiwi is None:
        return False
    try:
        tokens = kiwi.tokenize(surface.strip())
    except Exception:
        return False
    return bool(
        tokens and tokens[-1].tag == "EC"
        and any(token.tag.startswith(("VV", "VX")) for token in tokens)
        and all(token.tag in {"VV", "VX", "EC", "MAG", "MAJ"} for token in tokens)
    )


def _edition_modifier_context_before_title(before: str, title: str) -> bool:
    """Allow a new title after a time/discourse adjunct, never another owner."""
    base = _EDITION_MARKER_RE.sub("", title).strip()
    surface = re.search(r"(?<!\w)" + re.escape(base) + r"\s*$", before)
    if not surface:
        return False
    context = re.split(r"[.!?。;；]\s*", before[:surface.start()])[-1].strip()
    if not context:
        return True
    if context in _EDITION_DISCOURSE_ADJUNCTS or re.search(
        r"\]\s*(?:과|와|및|하고|랑)\s*$", context,
    ):
        return True
    kiwi = _edition_kiwi()
    if kiwi is None:
        return False
    try:
        tokens = kiwi.tokenize(context)
    except Exception:
        return False
    temporal = {"그", "이", "저", "뒤", "후", "오전", "오후", "오늘", "어제",
                "내일", "밤", "새벽", "저녁", "점심", "다음"}
    return bool(tokens and all(
        token.tag in {"MAG", "MAJ", "MM", "JKB", "JX", "VV", "VX", "EC"}
        or (token.tag == "NNG" and token.form in temporal)
        for token in tokens
    ) and not any(token.tag in {"VV", "VX"} for token in tokens)
        or _edition_discourse_connector(context))


def _edition_marker_adjacent_to_candidate(before: str, after: str, title: str) -> bool:
    base = _EDITION_MARKER_RE.sub("", title).strip()
    if not base:
        return False
    # Bound the title as a word so a different title ending in the same bytes
    # cannot lend its edition marker to this candidate.
    surface = re.sub(r"\\\s+", r"\\s+", re.escape(base))
    mention = re.search(r"(?<!\w)" + surface + r"(?:은|는|이|가|도)?\s*$", before)
    if mention:
        # A bare content word immediately before the candidate is part of a
        # longer title surface. Grammatical particles and time adverbs instead
        # mark ordinary sentence context around the exact candidate title.
        prefix = re.split(
            r"[.!?。;；]\s*|\S+(?:고|며|지만|는데|다가|더니)\s+",
            before[:mention.start()],
        )[-1]
        sentence_prefix = re.split(r"[.!?。;；]\s*", before[:mention.start()])[-1]
        prefix_words = prefix.rstrip(" ,\t'\"“‘`").split()
        if prefix_words:
            preceding = prefix_words[-1]
            source_possessive = bool(re.search(
                r"(?:^|[\s'\"“‘`])(?:(?:이|그|해당|내|제|우리)\s*"
                r"(?:글|게시글|게시물|포스트|본문)|"
                r"본문|원글|나|내|저|제)의\s*$", prefix,
            ))
            own_record_possessive = bool(re.search(
                r"(?:^|\s)(?:내|제|나의|저의)\s*(?:독서\s*)?"
                r"(?:기록|메모|독서일지|독후감|감상문)의\s*$", prefix,
            ))
            if preceding.endswith("의") and not (source_possessive or own_record_possessive):
                return False
            first_person_reading = bool(
                (preceding in {"계속", "꾸준히", "줄곧", "이미", "다시"}
                 or preceding.endswith("게")
                 or preceding.endswith(("뒤", "후"))
                 or (re.match(r"^(?:어젯?|오늘|내일|지난|이번|작년|올해)", preceding)
                     and preceding.endswith(("밤", "낮", "새벽", "아침", "저녁")))
                 or _edition_is_adverbial_modifier(preceding))
                and re.search(r"(?:^|\s)(?:나는|내가|저는|제가|나도|저도)\s+", prefix)
                and re.search(r"(?:읽|봤|보는|보고|감상|완독)", after[:50])
            )
            postposed_author_read = bool(
                preceding.endswith(("뒤", "후"))
                and re.match(r"^[을를]\s*(?:내가|나는|제가|저는)\s+.{0,20}(?:읽|완독|봤)", after)
            )
            self_speech_intro = bool(
                preceding == "말하길"
                and re.search(r"(?:^|\s)(?:나는|내가|저는|제가)\s+말하길\s*$", prefix)
                and re.match(r"^\s*[을를]\s*(?:읽|봤|정주행)", after)
            )
            relative_read_surface = bool(
                preceding == "정주행한"
                and re.search(r"(?:^|\s)[가-힣A-Za-z]{1,20}[은는이가]\s+", prefix)
            )
            post_reference_relative = _edition_current_post_prefix(prefix)
            first_person_relative = bool(
                re.search(r"(?:^|\s)(?:나는|내가|저는|제가|나도|저도)\s+", prefix)
                and re.search(r"(?:사랑한|사랑하는|읽었던|기다린|기다리던)$", preceding)
            )
            observed_relative = bool(
                preceding == "본"
                and re.search(r"(?:^|\s)(?:어제|오늘|내가|나는|제가|저는)\s+", prefix)
            )
            aspect_or_certainty = bool(
                (preceding in {"계속", "한참", "막"} and re.search(r"(?:읽|봤|보는|보고)", after[:50]))
                or (preceding == "분명" and re.match(r"^\s*(?:[이가은는]\s*)?이다", after))
            )
            # A discourse adverb before the title is clause context, while
            # a common noun or adnominal adjective can extend its title.
            discourse_modifier = False
            if re.match(r"^\s*[은는]\s+(?:내가|나는|제가|저는)\s+.{0,25}(?:읽|완독|봤)", after):
                kiwi = _edition_kiwi()
                if kiwi is not None:
                    try:
                        preceding_tokens = kiwi.tokenize(preceding)
                        discourse_modifier = bool(
                            len(preceding_tokens) == 1
                            and preceding_tokens[0].tag in {"MAG", "MAJ"}
                        )
                    except Exception:
                        pass
            transferred_to_author = bool(
                (preceding in {"빌려준", "건넨", "선물한", "사준"}
                 and re.search(r"(?:가|는|은)\s+(?:빌려준|건넨|선물한|사준)\s*$", prefix)
                 and re.search(r"(?:내가|나는|제가|저는)\s+.{0,20}(?:읽|봤)", after[:60]))
                or (preceding == "산"
                    and re.search(r"에게\s+산\s*$", prefix)
                    and re.search(r"(?:읽|봤)", after[:60]))
                or (
                    preceding in {"준", "추천한", "건넨", "선물한", "사준"}
                    and re.search(r"(?:빌려\s+준|추천한|건넨|선물한|사준)\s+" + surface + r"\s*$", before)
                    and re.match(
                        r"^\s*[을를]\s*(?:(?:오늘부터|어제부터|내가|나는|제가|저는)\s*){0,2}"
                        r"(?:읽|정주행|봤)",
                        after,
                    )
                )
                or (
                    preceding.endswith("준")
                    and re.search(r"(?:^|\s)(?:나는|내가|저는|제가)\s+", prefix)
                    and re.search(r"(?:^|\s)[가-힣A-Za-z]{1,20}[은는이가]\s+\S*준\s*$", prefix)
                    and re.match(r"^\s*[을를]\s+(?:\S+\s+){0,3}(?:읽|봤|정주행)", after)
                )
            )
            nominal_reader_after_transfer = bool(
                re.search(r"(?:^|\s)[^\s]+[은는이가]\s+[^\s]*준\s*$", prefix)
                and re.match(r"^[을를]\s*(?:읽은|본|정주행한)\s+사람[은는이가]\s+", after)
            )
            if (
                preceding not in {
                    "오늘", "어제", "내일", "요즘", "최근", "드디어", "방금",
                    "이번", "지금", "곧", "이제", "정말", "벌써", "오래",
                    "나는", "내가", "저는", "제가", "나도", "저도",
                }
                and not re.search(r"(?:은|는|이|가|도|을|를|의|에|에서|로|으로|던|린|룬|건)$", preceding)
                and not first_person_reading
                and not postposed_author_read
                and not self_speech_intro
                and not relative_read_surface
                and not post_reference_relative
                and not first_person_relative
                and not observed_relative
                and not aspect_or_certainty
                and not discourse_modifier
                and not transferred_to_author
                and not nominal_reader_after_transfer
                and not _edition_is_adverbial_modifier(preceding)
                and not _edition_discourse_connector(prefix)
                and not _edition_discourse_connector(sentence_prefix)
            ):
                return False
        return True
    return bool(re.match(r"^\s*" + surface + r"(?!\w)", after))


@dataclass(frozen=True)
class EditionMarkerMention:
    """One candidate-bound mention in an original source, before publication filtering."""

    candidate_title: str
    marker: str
    source_role: str
    source_index: int
    polarity: str  # asserted, denied, or reported
    quoted: bool
    current_post_relation: bool = False
    claim_status: str = "unresolved"
    reader_actor: str = "unknown"
    basis: str = ""
    evidence_span: Tuple[int, int] = (0, 0)
    pending: bool = False


@dataclass(frozen=True)
class EditionClaimEvent:
    """A source-spanned assertion about one candidate-bound edition marker."""

    marker_span: Tuple[int, int]
    evidence_span: Tuple[int, int]
    clause_role: str  # relative, main, correction, pending, rumor, or comment
    actor: str  # author, other, or unknown
    predicate: str  # read, identify, or record
    stance: str  # asserted, denied, reported, or unresolved
    current_post_relation: bool
    record_owner: str = "unknown"  # author, current_post, other, or unknown
    modality: str = "direct"  # direct, reported, future, question, or unknown


@dataclass(frozen=True)
class _EditionClaimLedger:
    """One marker claim with source-local roles and resolved event precedence."""

    claim_key: Tuple[str, int, int, str, Tuple[int, int]]
    clause_span: Tuple[int, int]
    reader_actor: str
    speaker_actor: str
    confirmer_actor: str
    target_relation: str  # bound, other, or unknown
    modality: str  # direct, reported, question, or unknown
    status: str  # asserted, denied, reported, unresolved, or fallback
    supersedes: Optional[Tuple[str, int, int, str, Tuple[int, int]]]
    events: Tuple[EditionClaimEvent, ...]
    edges: Tuple["_EditionClaimEdge", ...] = ()


@dataclass(frozen=True)
class _EditionClaimEdge:
    """A source-spanned relation between a marker claim and a later event."""

    kind: str  # supersedes or pending_verification
    claim_key: Tuple[str, int, int, str, Tuple[int, int]]
    event_span: Tuple[int, int]
    target: str  # current_post, own_record, or unknown


def _edition_clause_spans(line: str) -> Tuple[Tuple[int, int], ...]:
    """Keep strong stops and completed-predicate topic changes as source spans."""
    spans: List[Tuple[int, int]] = []
    start = 0
    for separator in re.finditer(r"[.!?。;；]|[,—:]", line):
        mark = separator.group()
        if mark in ",—:":
            preceding = line[start:separator.start()].rstrip()
            following = line[separator.end():]
            if not (
                re.search(r"(?:다|요|음|함|했음)$", preceding)
                and re.match(
                    r"\s*(?:\S+\s+){0,3}[가-힣A-Za-z]{1,20}[은는이가]\s+",
                    following,
                )
            ):
                continue
        spans.append((start, separator.start()))
        start = separator.end()
    spans.append((start, len(line)))
    return tuple(spans)


def _edition_claim_clause(line: str, marker_end: int) -> Tuple[int, int]:
    return next(
        (span for span in _edition_clause_spans(line) if span[0] <= marker_end <= span[1]),
        (marker_end, len(line)),
    )


def _edition_next_clause(line: str, clause_span: Tuple[int, int]) -> Optional[Tuple[int, int]]:
    clauses = _edition_clause_spans(line)
    index = next((i for i, span in enumerate(clauses) if span == clause_span), -1)
    return clauses[index + 1] if 0 <= index < len(clauses) - 1 else None


def _edition_followup_clause(
    line: str, clause_span: Tuple[int, int], next_line: str,
    line_break_len: int = 1,
) -> Optional[Tuple[int, int, str]]:
    """Find only the adjacent same-source clause, including a line break."""
    span = _edition_next_clause(line, clause_span)
    if span and line[slice(*span)].strip():
        return span[0], span[1], line[slice(*span)]
    if next_line.strip():
        start = len(line) + line_break_len
        return start, start + len(next_line), next_line
    return None


def _edition_statement_modality(line: str, match: re.Match[str]) -> str:
    """Read the candidate's clause, not a question in a later clause."""
    start, end = _edition_claim_clause(line, match.end())
    clause = line[start:end]
    if "?" in clause or line[end:end + 1] == "?":
        return "question"
    if re.search(r"(?:인지|는지|을지).{0,30}(?:묻|물었|질문)", clause):
        return "question"
    if re.search(r"(?:기록|노트).{0,55}" + re.escape(match.group()) +
                 r"\s*(?:완독|읽었|독서).{0,15}(?:착오|오류|틀렸)", clause):
        return "reported"
    completed_conjunct = re.search(r"(?:읽|완독|정주행|봤)(?:었|았|했)[가-힣]{0,3}고\s", clause)
    if completed_conjunct and completed_conjunct.start() > match.start() - start:
        return "direct"
    if re.search(
        r"(?:읽|보|정주행|완독|재독).{0,25}(?:예정|계획|겠다|겁니다)|"
        r"(?:읽|보|정주행|완독)\s*을\s*(?:것이다|생각이다)",
        clause,
    ):
        return "future"
    if re.search(r"(?:읽|보|정주행|완독|재독)(?:으려고|려고|어야겠|을\s*생각)", clause):
        return "future"
    if re.search(
        r"(?:다음\s*(?:달|주|해)|내일|모레).{0,25}"
        r"(?:읽|보|정주행|완독|재독)(?:는다|겠다|을\s*거|을\s*예정)",
        clause[match.end() - start:],
    ):
        return "future"
    if re.search(r"(?:읽|보|정주행|완독)(?:는|었다|었|다)?(?:다면|으면|면)", clause):
        return "conditional"
    return "direct"


def _edition_subject_actor(prefix: str) -> str:
    """Resolve an utterance's subject without treating adnominal verbs as nouns."""
    kiwi = _edition_kiwi()
    if kiwi is not None:
        try:
            tokens = kiwi.tokenize(prefix)
            subjects = [
                tokens[index - 1].form
                for index, token in enumerate(tokens)
                if index and (token.tag == "JKS" or
                              (token.tag == "JX" and token.form in {"은", "는", "도"}))
                and tokens[index - 1].tag in {"NP", "NNG", "NNP"}
            ]
            if subjects:
                return "author" if subjects[-1] in {"나", "내", "저", "제", "우리", "저희"} else "other"
            return "implicit"
        except Exception:
            pass
    subjects = re.findall(r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가도](?=\s|$)", prefix)
    subjects = [surface for surface in subjects if not re.search(r"(?:읽|보|봤|본|한)$", surface)]
    if not subjects:
        return "implicit"
    return "author" if subjects[-1] in {"나", "내", "저", "제", "우리", "저희"} else "other"


def _edition_adjunct_without_subject(prefix: str) -> bool:
    """Allow time/manner adjuncts before a review, never a new subject."""
    return not re.search(r"(?:^|\s)\S+[은는이가](?=\s|$)", prefix)


def _edition_document_target(fragment: str, source_role: str) -> str:
    """Bind a document's edition slot by possessor and deictic target."""
    slot = re.search(r"판본(?:\s*표기)?[을를은는]", fragment)
    if not slot:
        return "unknown"
    if re.search(r"(?:^|\s)(?:이|그|해당)\s+(?:글|독서일지|독후감|기록)(?:에|의)", fragment[:slot.start()]):
        return "current_post" if source_role == "post_body" else "other"
    owners = list(re.finditer(
        r"(?:^|\s)(?P<owner>내|제|나의|저의|이|그|해당|친구의|친구가|동료의|동료가)\s+",
        fragment[:slot.start()],
    ))
    if not owners:
        return "unknown"
    owner_match = owners[-1]
    owner = owner_match.group("owner")
    document = fragment[owner_match.end():slot.start()].strip()
    written_slot = bool(re.search(r"에\s*(?:적힌|쓴)$", document))
    document = re.sub(r"(?:에\s*적힌|에\s*쓴|의)$", "", document).strip()
    # A document about reading can be a memo, review, note, or article. A
    # shelf/room is a possession location, not a written edition claim.
    if not written_slot and not re.search(r"(?:독후감|독서노트|독서\s*기록|기록|메모|서평|감상문|평문|블로그\s*글|게시글|게시물|포스트|글)$", document):
        return "unknown"
    if owner in {"내", "제", "나의", "저의"}:
        return "own_record"
    if owner == "이" and source_role == "post_body":
        return "current_post"
    return "other"


def _edition_completed_revision(fragment: str) -> Optional[re.Match[str]]:
    """Recognize a completed change of a document's edition slot."""
    return re.search(
        r"(?P<slot>판본(?:\s*표기)?[을를은는])\s*(?:[가-힣]+\s+){0,2}"
        r"(?P<edition>단행본|연재본|개정판|합본|특별판|완전판|전자책|이북|ebook|e북)"
        r"으로\s*(?:[가-힣]+\s*){0,2}"
        r"(?P<verb>정정했|고쳤|바꿨|바로잡았|수정했|"
        r"(?:다시\s*)?(?:확인했|대조했|비교했|확인해\s*봤))"
        r"(?:다|습니다|어요|음|다고)?",
        fragment, flags=re.IGNORECASE,
    )


def _edition_followup_revision(fragment: str, marker: str) -> Optional[Tuple[str, Tuple[int, int]]]:
    """Resolve one adjacent edit to the same edition slot and source owner."""
    edition = r"단행본|연재본|개정판|합본|특별판|완전판|전자책|이북|ebook|e북"
    label = re.fullmatch(
        r"\s*(?:(?:그런데|하지만|다만)\s+)?"
        r"(?P<target>(?:(?:앞|위)(?:의|에\s*쓴|에서\s*쓴)|"
        r"위\s+문단의|"
        r"(?:이|그|해당)\s+(?:글|독서일지|독후감|기록)(?:에\s*쓴|의))\s*)"
        rf"(?P<edition>{edition})\s*(?:표기|판본|기록)(?:는|이)?\s*"
        rf"(?:틀렸|잘못됐|아니|오류였)(?:다|음|습니다|어요)?"
        rf"(?:고\s*(?:{edition})[이가]?\s*맞다)?\s*",
        fragment, flags=re.IGNORECASE,
    )
    if label and label.group("edition").casefold() == marker:
        return "denied", label.span()
    edit = re.fullmatch(
        r"\s*(?:(?:그런데|하지만|다만)\s+)?"
        r"(?P<target>(?:앞(?:서)?의|(?:이|그|해당)\s+"
        r"(?:글|독서일지|독후감|기록)(?:에\s*쓴|의))\s*)"
        rf"(?P<old>{edition})\s*(?:표기|판본|기록)(?:을|를)?\s*"
        rf"(?P<new>{edition})으로\s*(?:정정|수정|교체|고쳤|바꿨|바로잡았)"
        r"(?:했|하였)?(?:다|습니다|어요|음)?\s*",
        fragment, flags=re.IGNORECASE,
    )
    if edit and edit.group("old").casefold() == marker:
        return ("asserted" if edit.group("new").casefold() == marker else "denied", edit.span())
    return None


def _edition_future_verification(fragment: str) -> Optional[re.Match[str]]:
    """A verification plan is not a completed confirmation event."""
    return re.search(
        r"(?P<action>(?:비교|대조|확인)(?:해\s*보|하)?[가-힣\s]{0,12}?)"
        r"(?P<future>예정(?:이다|입니다|임)?|생각(?:이다|입니다|임)?|겠다)",
        fragment,
    )


def _edition_other_comment_document(prefix: str) -> bool:
    """A friend's post is not the original post addressed by a reply."""
    return bool(re.search(
        r"(?:^|\s)(?!이\s|그\s|해당\s|원글\s|본문\s|글\s|게시글\s|게시물\s|포스트\s)"
        r"[가-힣]{1,12}(?:의\s*|\s+)"
        r"(?:본문|글|게시글|게시물|포스트)(?:에|에서|의|\s)",
        prefix,
    ))


def _edition_projection_event(
    line: str, match: re.Match[str], source_role: str,
    following: str, events: Tuple[EditionClaimEvent, ...], *,
    denied: bool, reported: bool, other_account: bool, hearsay: bool,
    identifies_post: bool, quoted: bool, author_subject: bool,
    transferred_read: bool, direct_identification: bool,
    modality: str,
) -> Tuple[EditionClaimEvent, ...]:
    """Represent direct source claims as events before the sole claim reducer."""
    span = (match.start(), match.end())
    clause = _edition_claim_clause(line, match.end())
    question = "?" in line[slice(*clause)] or line[clause[1]:clause[1] + 1] == "?"
    if modality != "direct":
        return events
    if transferred_read and not re.match(
        r"^[을를]\s*(?:읽은|본|정주행한)\s+(?:사람|건|게)", following,
    ):
        events = tuple(
            replace(event, actor="author", stance="asserted", current_post_relation=True)
            if event.predicate == "read" and event.clause_role == "main" and event.actor == "other"
            else event for event in events
        )
    if denied and not question and not other_account and not hearsay and (
        source_role != "comment" or identifies_post
    ) and not any(
        event.stance == "denied" for event in events
    ):
        events = (*events, EditionClaimEvent(
            marker_span=span, evidence_span=(match.end(), _edition_claim_clause(line, match.end())[1]),
            clause_role="main", actor="author", predicate="identify",
            stance="denied", current_post_relation=True,
        ))
    if events or question or reported or other_account or hearsay:
        return events
    if re.match(
        r"^[은는이가도을를]?\s*(?:겉표지|표지(?:\s*사진)?|삽화|이미지|그림|썸네일|목차)"
        r"(?:만|을|를)?\s*(?:봤|보았|본|구경했)",
        following.strip(),
    ):
        # Seeing auxiliary art is not reading the named work.
        return events
    if re.match(
        r"^[을를]\s*(?:읽은|본|정주행한)\s+"
        r"[가-힣]{1,8}[은는이가]\s+",
        following,
    ):
        # A reader-role statement must bind its named reader first. An
        # unsupported role surface cannot become implicit author reading.
        return events
    direct_surface = bool(
        source_role == "post_title"
        or (source_role == "comment" and identifies_post)
        or (source_role == "post_body" and (
            _DIRECT_EDITION_USE_RE.search(following[:40])
            or re.search(r"(?:완독|정주행|갖고\s*있|소장)(?:했|한|한다|했다|다|음)?", following[:40])
            and (author_subject or not re.search(r"(?:갖고|소장)", following[:40]))
            or re.match(r"^(?:이라고|라고)\s*(?:내가|나는|제가|저는)\s+말", following)
            or direct_identification
            or re.fullmatch(
                r"[이가은는]?\s*맞다고\s*(?:내가|제가|나는|저는)\s*"
                r"(?:직접\s*)?(?:확인|검증)(?:한다|합니다|했다|했습니다)",
                following.strip(),
            )
            or re.match(r"^(?:[은는이가도]\s*)?(?:이다|입니다|임|맞음|맞다|맞습니다|출간)(?![가-힣])", following)
            or not following.strip()
        ))
    )
    if not direct_surface or (quoted and source_role != "post_title" and not _DIRECT_EDITION_USE_RE.search(following[:40])):
        return events
    predicate = "read" if re.search(r"(?:읽|봤|(?<![가-힣])본(?=\s|$)|정주행|완독|재독)", following[:40]) else "identify"
    return (*events, EditionClaimEvent(
        marker_span=span,
        evidence_span=(match.start(), _edition_claim_clause(line, match.end())[1]),
        clause_role="main" if source_role == "post_body" else source_role,
        actor="author", predicate=predicate, stance="asserted",
        current_post_relation=True,
    ))


@lru_cache(maxsize=1)
def _edition_kiwi() -> Any:
    try:
        from kiwipiepy import Kiwi
        return Kiwi()
    except Exception:
        return None


def _relative_read_actor(prefix: str) -> str:
    """Find the subject of the adnominal reading, excluding time adverbs."""
    if not re.search(r"(?:읽은|읽었던|본|봤던|정주행한)\s*$", prefix):
        return "unknown"
    kiwi = _edition_kiwi()
    if kiwi is None:
        return "unknown"
    try:
        tokens = kiwi.tokenize(prefix)
    except Exception:
        return "unknown"
    subjects = [
        tokens[index - 1].form
        for index, token in enumerate(tokens)
        if index and (token.tag == "JKS" or (token.tag == "JX" and token.form in {"은", "는", "도"}))
        and tokens[index - 1].tag in {"NP", "NNG", "NNP"}
    ]
    if not subjects:
        return "implicit"
    return "author" if subjects[-1] in {"나", "저", "우리"} else "other"


def _edition_claim_events(
    line: str, match: re.Match[str], source_role: str, local_prefix: str,
    next_line: str = "",
    line_break_len: int = 1,
) -> Tuple[EditionClaimEvent, ...]:
    """Extract decisive events; an unresolved event cannot authorize publication."""
    after = line[match.end():].lstrip(" \t'\"”’`")
    clause_span = _edition_claim_clause(line, match.end())
    # Keep the original source offset while bounding the reader's clause.
    raw_body_after = line[match.end():clause_span[1]] if source_role == "post_body" else line[match.end():]
    body_after = raw_body_after.lstrip(" \t'\"”’`")
    body_after_start = match.end() + len(raw_body_after) - len(body_after)
    marker = match.group(1).casefold()
    span = (match.start(), match.end())
    events: List[EditionClaimEvent] = []

    if source_role == "post_body":
        enclosure = next((
            quote for quote in re.finditer(
                r"'[^']*'|\"[^\"]*\"|“[^”]*”|‘[^’]*’|`[^`]*`", line,
            ) if quote.start() <= match.start() < quote.end()
        ), None)
        if enclosure and _edition_subject_actor(line[:enclosure.start()]) == "author":
            quoted_claim = line[enclosure.start() + 1:enclosure.end() - 1]
            outside = line[enclosure.end():clause_span[1]].strip()
            if (re.search(r"(?:^|\s)이\s+(?:책|작품|소설)[은는이가]", quoted_claim)
                    and re.search(r"(?:이다|입니다|맞다)\s*$", quoted_claim)
                    and re.fullmatch(
                        r"(?:이?라고|라고)\s*직접\s*(?:확인|검증)"
                        r"(?:함|했(?:습니다|어요|다))",
                        outside,
                    )):
                events.append(EditionClaimEvent(
                    marker_span=span, evidence_span=(enclosure.start(), clause_span[1]),
                    clause_role="main", actor="author", predicate="identify",
                    stance="asserted", current_post_relation=True,
                ))

    relative = re.search(r"(?:읽은|읽었던|본|봤던|정주행한)\s*$", local_prefix)
    if relative:
        actor = _relative_read_actor(local_prefix)
        if source_role == "comment":
            # A reply's first person is its writer, not the post author.
            actor = "other"
        if actor not in {"other", "implicit"}:
            prefix_start = line.rfind(local_prefix, 0, match.start())
            if prefix_start < 0:
                prefix_start = 0
            events.append(EditionClaimEvent(
                marker_span=span,
                evidence_span=(prefix_start + relative.start(), prefix_start + relative.end()),
                clause_role="relative", actor=actor, predicate="read",
                stance="asserted" if actor == "author" else "reported",
                current_post_relation=actor == "author",
            ))

    # A completed reading inside the source author's own record or the
    # directly identified book remains their event. The noun after the
    # adnominal verb names the record/object; it is not a second reader.
    if source_role == "post_body" and not any(event.predicate == "read" for event in events):
        governed_read = re.search(
            r"(?P<actor>(?:나|내|저|제|우리|저희|형|친구|동생|누나))[은는이가]\s*"
            r"(?:\S+\s+){0,4}?(?:읽은|읽고|완독한)\s*(?:책|독서일지|독후감|기록)",
            line[:match.start()] + body_after,
        )
        first_person_embedded = re.search(
            r"(?P<actor>(?:나|내|저|제|우리|저희|형|친구|동생|누나))[은는이가]\s*"
            r"[^.!?。]{0,60}?" + re.escape(line[match.start():match.end()]) +
            r"[을를]\s*(?:끝까지\s*)?읽고\s+남긴\s*(?:것|글|기록|독서일지)",
            line,
        )
        if (governed_read or first_person_embedded) and (
            (governed_read or first_person_embedded).group("actor")
            in {"나", "내", "저", "제", "우리", "저희"}
        ):
            events.append(EditionClaimEvent(
                marker_span=span,
                evidence_span=((governed_read or first_person_embedded).start(),
                               min(clause_span[1], match.end() + len(body_after))),
                clause_role="relative", actor="author", predicate="read",
                stance="asserted", current_post_relation=True,
            ))

    if source_role == "post_body" and not any(event.predicate == "read" for event in events):
        own_record_read = bool(
            re.search(r"(?:^|\s)(?:이|그|해당)\s*(?:감상문|독서일지|독후감|기록)(?:에는|에|의)",
                      local_prefix)
            and re.search(r"(?:^|\s)(?:내가|나는|제가|저는)\s*$", local_prefix)
            and re.match(r"^[을를]\s*읽었다고\s+직접\s*(?:적었|썼)", body_after)
        )
        reaffirmed_read = bool(
            re.search(r"(?:^|\s)(?:내가|나는|제가|저는)\s*$", local_prefix)
            and re.match(r"^[을를]\s*읽은\s*게\s+맞다\s*$", body_after)
        )
        if own_record_read or reaffirmed_read:
            events.append(EditionClaimEvent(
                marker_span=span, evidence_span=(match.start(), clause_span[1]),
                clause_role="main", actor="author", predicate="read",
                stance="asserted", current_post_relation=True,
            ))

    auxiliary_art = bool(re.match(
        r"^[은는이가도을를]?\s*(?:겉표지|표지(?:\s*사진)?|삽화|이미지|그림|썸네일|목차)"
        r"(?:만|을|를)?\s*(?:봤|보았|본|구경했)", body_after,
    ))
    main_reader = None if auxiliary_art else re.match(
        r"^[을를은는]\s*(.{0,70}?)(?:읽|봤|정주행|완독|재독)(?:었|았|습|고|음|다|했)", body_after,
    )
    if main_reader and not re.search(r"(?:소문|읽은\s*(?:건|게))", body_after):
        before_verb = main_reader.group(1)
        post_subjects = list(re.finditer(
            r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가](?=\s)", before_verb,
        ))
        prefix_subjects = list(re.finditer(
            r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가](?=\s)", local_prefix,
        ))
        self_subjects = {"나", "내", "저", "제", "우리", "저희"}
        if post_subjects:
            actor = "author" if post_subjects[-1].group(1) in self_subjects else "other"
        elif prefix_subjects and prefix_subjects[0].group(1) in self_subjects:
            actor = "author"
        else:
            # A topic before a relative clause can name a lender, time, or
            # this post; without a post-marker reader it is not a main actor.
            actor = "unknown"
    else:
        main_reader = None
        actor = "unknown"
    quoted_other_speaker = bool(re.search(
        r"(?:^|\s)[가-힣]{1,20}[은는이가]\s*['\"“‘]\s*$", local_prefix,
    ) and not re.search(r"(?:^|\s)(?:나는|내가|저는|제가)\s*['\"“‘]\s*$", local_prefix))
    if main_reader and actor != "unknown":
        if source_role == "comment":
            actor = "other"
        events.append(EditionClaimEvent(
            marker_span=span,
            evidence_span=(match.end(), match.end() + main_reader.end()),
            clause_role="main", actor=actor, predicate="read",
            stance="asserted" if actor == "author" and not quoted_other_speaker else "reported",
            current_post_relation=actor == "author" and not quoted_other_speaker,
        ))

    # A quotation can be the author's own direct reading statement. Bind
    # both the quoted reader and the reporting speaker before asserting it;
    # a friend's quotation or an unconfirmed report remains non-authoritative.
    quoted_reader = re.match(
        r"^[을를]\s*(?:읽은|본|정주행한)\s+(?:사람|독자)[은는이가]\s+"
        r"(?:나|저|내가|제가)(?:\s*맞다|[이가]\s*맞다)?['\"”’]\s*(?:라고|고)\s*"
        r"직접\s*(?:말했|밝혔|확인했)(?:다|습니다|어요)",
        body_after,
    )
    quoted_by_author = bool(re.search(
        r"(?:^|\s)(?:나는|내가|저는|제가)\s*['\"“‘]\s*$", local_prefix,
    ))
    if source_role == "post_body" and quoted_reader and quoted_by_author:
        events.append(EditionClaimEvent(
            marker_span=span,
            evidence_span=(match.end(), body_after_start + quoted_reader.end()),
            clause_role="main", actor="author", predicate="read",
            stance="asserted", current_post_relation=True,
        ))

    # The reader in "읽은 사람은 X" is X. The subject, recipient, and time
    # of a later confirmation are separate roles. Even a nonassertive clause
    # needs an event so the legacy mention fallback cannot publish it.
    nominal_reader = re.match(
        r"^[을를]\s*(?:읽은|본|정주행한)\s+"
        r"(?:(?:사람|독자)[은는이가]|(?:게|건))\s+(?:바로\s+)?"
        r"(?P<reader>[가-힣A-Za-z]{1,20}?)(?P<negative>\s+아니)?"
        r"(?:였다고|이었다고|라고|[이가]\s+맞다고|"
        r"(?P<direct>[이가]\s*맞다|이었다|였다|입니다|이다|다))"
        r"(?P<followup>.*)$",
        body_after.strip(),
    )
    reported_reader = re.match(
        r"^[을를]\s*(?:읽은|본|정주행한)\s+사람[은는이가]\s+"
        r"(?P<reader>[가-힣A-Za-z]{1,20}?)라는\s+(?:전언|소문|얘기)(?:이었|이었다|이다|이)?",
        body_after.strip(),
    )
    reader_claim = nominal_reader or reported_reader
    if source_role == "post_body" and reader_claim:
        reader = reader_claim.group("reader")
        reader_is_author = reader in {"나", "저", "내", "제", "내가", "제가"}
        followup = nominal_reader.group("followup").strip() if nominal_reader else ""
        direct_reader = bool(nominal_reader and nominal_reader.group("direct"))
        confirmation_end = match.end() + len(body_after)
        if direct_reader and not followup.strip(" .!。"):
            next_span = _edition_next_clause(line, clause_span)
            if next_span:
                followup = line[slice(*next_span)].strip()
                confirmation_end = next_span[1]
        confirmation = re.fullmatch(
            r"(?P<adjunct>.*?)\s*(?:직접\s*확인(?:했다|했습니다|했어요|함)|"
            r"분명히\s*밝혔다)\s*[.!。!]*",
            followup,
        )
        confirmer = None
        adjunct_scope_safe = True
        if confirmation:
            adjunct = confirmation.group("adjunct").strip()
            if adjunct:
                kiwi = _edition_kiwi()
                if kiwi is None:
                    adjunct_scope_safe = False
                else:
                    try:
                        adjunct_scope_safe = all(
                            token.tag in {"NNG", "NNP", "NP", "NR", "MAG", "JKS", "JX", "JKB"}
                            for token in kiwi.tokenize(adjunct)
                        )
                    except Exception:
                        adjunct_scope_safe = False
            subjects = list(re.finditer(
                r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가](?=\s|$)",
                confirmation.group("adjunct"),
            ))
            if subjects:
                confirmer = subjects[-1].group(1)
        confirmed_by_author = confirmer is None or confirmer in {"나", "내", "저", "제"}
        reported_intro = bool(re.search(
            r"(?:말하길|전언|들었는데|들었다|말했는데)\s*$", local_prefix,
        ))
        direct_statement = direct_reader and not followup.strip(" .!。")
        asserted = bool(
            nominal_reader and reader_is_author and not nominal_reader.group("negative")
            and (confirmation or direct_statement)
            and adjunct_scope_safe and confirmed_by_author and not reported_intro
            and line[clause_span[1]:clause_span[1] + 1] != "?"
        )
        events.append(EditionClaimEvent(
            marker_span=span,
            evidence_span=(match.end(), confirmation_end),
            clause_role="main", actor="author" if reader_is_author else "other",
            predicate="read", stance="asserted" if asserted else "reported",
            current_post_relation=asserted,
        ))

    sequential_read = re.match(
        r"^[을를]\s*(?:읽|보|정주행)(?:은|었던|한)\s*(?:뒤|후|다음)", body_after,
    )
    if source_role == "post_body" and sequential_read:
        preceding_subjects = list(re.finditer(
            r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가](?=\s|$)", local_prefix,
        ))
        actor = (
            "author" if not preceding_subjects or preceding_subjects[-1].group(1)
            in {"나", "내", "저", "제", "우리", "저희"} else "other"
        )
        events.append(EditionClaimEvent(
            marker_span=span,
            evidence_span=(body_after_start, body_after_start + sequential_read.end()),
            clause_role="main", actor=actor, predicate="read",
            stance="asserted" if actor == "author" else "reported",
            current_post_relation=actor == "author",
        ))

    record = re.search(r"(?:메모|기록|적|기재|써\s*뒀|썼).{0,30}", body_after)
    if record:
        events.append(EditionClaimEvent(
            marker_span=span,
            evidence_span=(body_after_start + record.start(), body_after_start + record.end()),
            clause_role="record", actor="unknown", predicate="record",
            stance="unresolved", current_post_relation=False,
            record_owner="other" if source_role == "comment" else "author",
            modality="unknown",
        ))
        final_editions = list(re.finditer(
            r"(?:단행본|연재본|개정판|합본|특별판|완전판|전자책|이북|ebook|e북)",
            body_after, flags=re.IGNORECASE,
        ))
        if final_editions:
            final = final_editions[-1]
            final_review = bool(re.search(
                r"(?:대조|비교)해\s*보니", body_after[record.start():final.start()],
            ))
            contrasted = final_review or bool(re.search(
                r"(?:으나|지만|다가|정정|고쳤|실제|확인하니)",
                body_after[record.start():final.start()],
            ))
            confirmed = final_review or bool(re.search(
                r"(?:확정|확인|그대로|실제|대조해\s*보니|판본도)", body_after[record.start():],
            ))
            if (final.group().casefold() != marker and contrasted) or (
                final.group().casefold() == marker and confirmed
            ):
                stance = "denied" if final.group().casefold() != marker else "asserted"
                events.append(EditionClaimEvent(
                    marker_span=span,
                    evidence_span=(match.end() + record.start(), match.end() + final.end()),
                    clause_role="correction", actor="author", predicate="record",
                    stance=stance, current_post_relation=True,
                ))
        elif source_role == "post_body":
            # The immediately following clause can explicitly revise the
            # recorded edition without repeating the work name. Do not borrow
            # an unrelated later reader or an unqualified edition mention.
            next_span = _edition_next_clause(line, clause_span)
            if next_span:
                next_clause = line[slice(*next_span)].strip()
                review = re.search(
                    r"(?:다시\s*)?(?:비교|대조|확인)해\s*보니\s*"
                    r"(?P<edition>단행본|연재본|개정판|합본|특별판|완전판|전자책|이북|ebook|e북)",
                    next_clause, flags=re.IGNORECASE,
                )
                if review and _edition_adjunct_without_subject(next_clause[:review.start()]):
                    final_marker = review.group("edition").casefold()
                    events.append(EditionClaimEvent(
                        marker_span=span,
                        evidence_span=(
                            match.end() + record.start(),
                            next_span[0] + (len(line[slice(*next_span)]) - len(line[slice(*next_span)].lstrip()))
                            + review.end("edition"),
                        ),
                        clause_role="correction", actor="author", predicate="record",
                        stance="asserted" if final_marker == marker else "denied",
                        current_post_relation=True,
                    ))
                # A note scheduled for later verification is not a resolved
                # edition claim. Keep it in the ledger to close the fallback.
                pending = _edition_future_verification(next_clause)
                if pending and not review and not any(
                    event.predicate == "read" and event.stance == "asserted"
                    for event in events
                ) and _edition_adjunct_without_subject(next_clause[:pending.start()]):
                    events.append(EditionClaimEvent(
                        marker_span=span,
                        evidence_span=(next_span[0] + pending.start(), next_span[0] + pending.end()),
                        clause_role="pending", actor="unknown", predicate="record",
                        stance="reported", current_post_relation=False,
                        record_owner="author", modality="future",
                    ))

    # An explicit retraction followed immediately by a bare final edition is
    # a source-bound correction. An unrelated intervening subject is not.
    if source_role == "post_body" and re.search(
        r"(?:잘못\s*알|오보|추측.{0,12}틀|기억.{0,12}틀)", body_after,
    ):
        clauses = _edition_clause_spans(line)
        clause_index = next((i for i, item in enumerate(clauses) if item == clause_span), -1)
        if 0 <= clause_index < len(clauses) - 1:
            next_span = clauses[clause_index + 1]
            next_text = line[slice(*next_span)].lstrip()
            final = re.match(
                r"(?P<edition>단행본|연재본|개정판|합본|특별판|완전판|전자책|이북|ebook|e북)"
                r"(?:이다|입니다|이었다|였다|\s+감상|\s+맞음)?",
                next_text, flags=re.IGNORECASE,
            )
            if final:
                final_marker = final.group("edition").casefold()
                events.append(EditionClaimEvent(
                    marker_span=span,
                    evidence_span=(
                        match.end(),
                        next_span[0] + len(line[slice(*next_span)]) - len(next_text)
                        + final.end("edition"),
                    ),
                    clause_role="correction", actor="author", predicate="record",
                    stance="asserted" if final_marker == marker else "denied",
                    current_post_relation=True,
                ))

    # A direct change to this post or the author's own record supersedes the
    # prior edition claim. A friend's separate review/record has another owner.
    if source_role == "post_body":
        followup = _edition_followup_clause(line, clause_span, next_line, line_break_len)
        if followup:
            next_start, _, next_raw = followup
            next_text = next_raw.strip()
            revision = _edition_completed_revision(next_text)
            target = _edition_document_target(next_text[:revision.end("slot")], source_role) if revision else "unknown"
            prior_subjects = list(re.finditer(
                r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가](?=\s|$)",
                local_prefix,
            ))
            prior_other_reader = bool(
                prior_subjects
                and prior_subjects[-1].group(1) not in {"나", "내", "저", "제", "우리", "저희"}
                and not re.search(r"(?:읽은|본|건넨|선물한|추천한|빌려준)\s*$", local_prefix)
            )
            if revision and target in {"own_record", "current_post"} and (
                target == "own_record" or not prior_other_reader
            ):
                subjects = list(re.finditer(
                    r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가](?=\s)",
                    next_text[:revision.start()],
                ))
                owner_start = next((
                    item.start() for item in re.finditer(
                        r"(?:^|\s)(?:내|제|나의|저의)\s+",
                        next_text[:revision.start()],
                    )
                ), None)
                if owner_start is not None and subjects:
                    kiwi = _edition_kiwi()
                    if kiwi is not None:
                        governed = []
                        for subject in subjects:
                            if subject.end() >= owner_start:
                                governed.append(subject)
                                continue
                            between = next_text[subject.end():owner_start]
                            try:
                                tags = [token.tag for token in kiwi.tokenize(between)]
                            except Exception:
                                tags = []
                            if not (any(tag.startswith(("VV", "VA")) for tag in tags)
                                    and any(tag in {"EC", "ETM"} for tag in tags)):
                                governed.append(subject)
                        subjects = governed
                explicit_author = bool(
                    subjects and subjects[-1].group(1) in {"나", "내", "저", "제"}
                )
                subject_is_other = bool(subjects and not explicit_author)
                if not subject_is_other:
                    final_marker = revision.group("edition").casefold()
                    other_only_read = prior_other_reader or any(
                        event.predicate == "read" and event.actor == "other"
                        for event in events
                    ) and not any(
                        event.predicate == "read" and event.actor == "author"
                        for event in events
                    )
                    # Changing an author's review after somebody else's read
                    # does not claim that the author read that edition. A
                    # direct check of the author's reading record does.
                    if not (other_only_read and final_marker == marker
                            and not re.search(r"확인|대조|비교", revision.group("verb"))):
                        events.append(EditionClaimEvent(
                            marker_span=span,
                            evidence_span=(
                                next_start + len(next_raw) - len(next_raw.lstrip()),
                                next_start + len(next_raw) - len(next_raw.lstrip())
                                + revision.end(),
                            ),
                            clause_role="correction", actor="author", predicate="record",
                            stance="asserted" if final_marker == marker else "denied",
                            current_post_relation=True,
                            record_owner="author" if target == "own_record" else "current_post",
                        ))

    # A same-marker correction to the immediately preceding label retracts
    # that label even when it does not repeat the work name. The deictic
    # reference and the edition must both resolve in the adjacent source span.
    if source_role == "post_body":
        followup = _edition_followup_clause(line, clause_span, next_line, line_break_len)
        if followup:
            next_start, _, next_text = followup
            revision = _edition_followup_revision(next_text, marker)
            if revision:
                stance, revision_span = revision
                events.append(EditionClaimEvent(
                    marker_span=span,
                    evidence_span=(next_start + revision_span[0],
                                   next_start + revision_span[1]),
                    clause_role="correction", actor="author", predicate="record",
                    stance=stance, current_post_relation=True,
                    record_owner="current_post",
                ))

    # A completed comparison/confirmation of the same recorded edition is a
    # source-bound event, whether its result is in this clause or the next.
    if source_role == "post_body" and not any(
        event.stance == "asserted" and event.current_post_relation for event in events
    ) and (
        not re.search(r"(?:^|\s)\S+[은는이가]\s*$", local_prefix)
        or re.search(r"(?:^|\s)(?:내가|나는|제가|저는)\s*$", local_prefix)
    ):
        next_span = _edition_next_clause(line, clause_span)
        if next_span:
            next_text = line[slice(*next_span)].strip()
            confirmation = re.fullmatch(
                r"(?:지금도|오늘도|오늘|다시)?\s*(?:그|이|해당)\s*"
                r"(?:(?:" + re.escape(marker) + r")\s*)?"
                r"(?:기록|표기|판본)(?:이|가)\s*맞다고\s*"
                r"(?:(?:내가|제가|나는|저는)\s*)?(?:직접\s*)?"
                r"(?:확인|검증)(?:한다|했다|함|했습니다)",
                next_text,
            )
            own_record = bool(re.search(
                r"(?:^|\s)(?:옛|내|제|나의|저의)\s*(?:독서\s*)?기록", local_prefix,
            ))
            self_confirmation = bool(re.search(
                r"(?:내가|제가|나는|저는)\s*(?:직접\s*)?(?:확인|검증)", next_text,
            ) or re.search(r"(?:^|\s)(?:내가|나는|제가|저는)\s+", local_prefix))
            if confirmation and self_confirmation and (
                own_record or re.search(r"(?:^|\s)(?:내가|나는|제가|저는)\s+", local_prefix)
            ):
                events.append(EditionClaimEvent(
                    marker_span=span,
                    evidence_span=(next_span[0], next_span[0] + len(line[slice(*next_span)])),
                    clause_role="correction", actor="author", predicate="record",
                    stance="asserted", current_post_relation=True,
                    record_owner="author",
                ))
        same_result = re.search(
            r"(?:실제|다시\s*확인(?:해\s*보니)?).{0,22}?"
            + re.escape(marker) + r"(?:이었|였다|이다|입니다|임|\s+감상)",
            body_after,
        )
        next_span = _edition_next_clause(line, clause_span)
        if not same_result and next_span and re.search(r"(?:기억|메모|적|써).{0,35}확인했", body_after):
            next_text = line[slice(*next_span)]
            next_result = re.match(r"\s*역시\s*" + re.escape(marker) + r"(?:\s+감상|이었다|였다|이다)", next_text)
            if next_result:
                same_result_span = (next_span[0], next_span[0] + next_result.end())
            else:
                same_result_span = None
        else:
            same_result_span = (
                (body_after_start + same_result.start(), body_after_start + same_result.end())
                if same_result else None
            )
        if same_result_span:
            events.append(EditionClaimEvent(
                marker_span=span, evidence_span=same_result_span,
                clause_role="correction", actor="author", predicate="record",
                stance="asserted", current_post_relation=True,
                record_owner="author",
            ))

    # Confirmation is an event over the book or edition slot named before
    # the marker. Its actor and target are independent of earlier reading.
    current_book = _edition_current_book_target(local_prefix)
    confirmed_book = current_book and _edition_completed_identification(body_after)
    author_certainty = bool(
        source_role == "post_body" and current_book
        and re.fullmatch(
            r"(?:이?라고|라고)\s*(?:내가|나는|제가|저는)\s*"
            r"(?:이제|지금|오늘)?\s*(?:확실히\s*안다|확신한다)", body_after.strip(),
        )
    )
    if confirmed_book or author_certainty:
        events.append(EditionClaimEvent(
            marker_span=span, evidence_span=(match.start(), clause_span[1]),
            clause_role="comment" if source_role == "comment" else "main",
            actor="author", predicate="identify", stance="asserted",
            current_post_relation=True,
        ))
    own_record = bool(re.search(
        r"(?:^|\s)(?:내|제|나의|저의)\s*(?:독서\s*)?"
        r"(?:기록|메모|독서일지|독후감|감상문)의\s*$", local_prefix,
    ))
    if (source_role == "post_body" and own_record and re.fullmatch(
        r"(?:판본|표기)(?:이|가)\s*맞음(?:을|을\s*직접)?\s*"
        r"(?:직접\s*)?(?:확인|검증)(?:했다|했습니다|했어요|함)",
        body_after.strip(),
    )):
        events.append(EditionClaimEvent(
            marker_span=span, evidence_span=(match.start(), clause_span[1]),
            clause_role="main", actor="author", predicate="record",
            stance="asserted", current_post_relation=True, record_owner="author",
        ))

    rumor = re.search(r"(?:읽|봤|정주행).{0,12}소문", body_after)
    if rumor:
        events.append(EditionClaimEvent(
            marker_span=span,
            evidence_span=(match.end() + rumor.start(), match.end() + rumor.end()),
            clause_role="rumor", actor="unknown", predicate="read",
            stance="reported", current_post_relation=False,
        ))

    if source_role == "comment":
        current_ref = _edition_current_post_prefix(local_prefix) and not _edition_other_comment_document(local_prefix)
        self_quoted = bool(re.search(
            r"(?:^|\s)(?:내가|나는|제가|저는)\s+['\"“‘].*"
            r"(?:원글|본문|(?:이|그)\s*글)의\s*$",
            local_prefix,
        ))
        direct = bool(re.fullmatch(
            r"(?:맞음|이?라고\s*단언함|인\s*게\s*확실(?:함|하다|합니다))\s*[.!。!]*",
            after.strip(),
        ))
        quoted_self_direct = bool(re.fullmatch(
            r"맞음['\"”’]\s*(?:이라고|라고)\s*주장(?:한다|했다)",
            line[match.end():].strip(),
        ))
        if (current_ref and direct) or (self_quoted and quoted_self_direct):
            events.append(EditionClaimEvent(
                marker_span=span,
                evidence_span=(match.end(), len(line)),
                clause_role="comment", actor="author", predicate="identify",
                stance="asserted", current_post_relation=True,
            ))
    return tuple(events)


def _edition_claim_ledger(
    line: str, match: re.Match[str], source_role: str, source_index: int,
    line_index: int, candidate_key: str, events: Tuple[EditionClaimEvent, ...], quoted: bool,
) -> _EditionClaimLedger:
    """Resolve one marker's source-local events before projecting a mention."""
    claim_key = (source_role, source_index, line_index, candidate_key,
                 (match.start(), match.end()))
    clause_span = _edition_claim_clause(line, match.end())
    clause = line[slice(*clause_span)]
    read_events = [event for event in events if event.predicate == "read"]
    reader_actor = read_events[-1].actor if read_events else "unknown"
    correction = next((
        event for event in reversed(events)
        if event.clause_role == "correction" and event.current_post_relation
        and event.stance in {"asserted", "denied"}
    ), None)
    direct = [event for event in events if event.stance == "asserted" and event.current_post_relation]
    denial = [event for event in events if event.stance == "denied" and event.current_post_relation]
    structured = not quoted and bool(re.search(
        r"[을를]\s*(?:읽은|본|정주행한)\s+사람[은는이가]|"
        r"(?:이라고|으로)\s*(?:메모|기록|적|기재|써\s*뒀|썼)",
        clause,
    ))
    if denial:
        status = "denied"
    elif direct:
        status = "asserted"
    elif events and all(event.stance == "unresolved" for event in events):
        status = "unresolved"
    elif events:
        status = "reported"
    elif structured:
        status = "unresolved"
    else:
        status = "fallback"
    confirmer = re.search(r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가]\s+직접\s*확인", clause)
    if confirmer:
        confirmer_actor = (
            "author" if confirmer.group(1) in {"나", "내", "저", "제"} else "other"
        )
    elif re.search(r"직접\s*확인", clause) and not re.search(r"전언|소문|얘기", clause):
        confirmer_actor = "author"
    else:
        confirmer_actor = "unknown"
    speaker_actor = (
        "other" if confirmer_actor == "other" else "author" if reader_actor == "other"
        else "unknown" if status in {"reported", "unresolved"} else "author"
    )
    target_relation = (
        "bound" if any(event.current_post_relation for event in events)
        else "other" if reader_actor == "other" else "unknown"
    )
    edges = tuple(
        _EditionClaimEdge(
            kind="supersedes" if event.clause_role == "correction" else "pending_verification",
            claim_key=claim_key, event_span=event.evidence_span,
            target="current_post" if event.record_owner == "current_post" else
            "own_record" if event.record_owner == "author" else "unknown",
        )
        for event in events
        if event.clause_role in {"correction", "pending"}
    )
    return _EditionClaimLedger(
        claim_key=claim_key, clause_span=clause_span, reader_actor=reader_actor,
        speaker_actor=speaker_actor, confirmer_actor=confirmer_actor,
        target_relation=target_relation,
        modality="question" if "?" in line[clause_span[1]:clause_span[1] + 1]
        else "reported" if status == "reported" and speaker_actor != "author"
        else "direct" if status in {"asserted", "reported"}
        else "unknown",
        status=status, supersedes=claim_key if correction else None, events=events,
        edges=edges,
    )


@dataclass(frozen=True)
class EditionNativeSource:
    source_id: str
    source_role: str
    source_index: int
    raw_text: str
    used_text: str
    raw_text_sha256: str
    used_text_sha256: str
    boundary_map: Tuple[Tuple[int, int], ...]
    coordinate_system: str = "NFKC_unicode_code_points"
    raw_coordinate_system: str = "raw_unicode_code_points"


@dataclass(frozen=True)
class EditionNativeSpan:
    source_id: str = ""
    source_index: int = -1
    used_span: Tuple[int, int] = ()
    used_text: str = ""
    raw_span: Tuple[int, int] = ()
    raw_text: str = ""
    status: str = "NOT_OBSERVED"
    reason: str = "parser_did_not_select_a_source_span"
    coordinate_system: str = "NFKC_unicode_code_points"
    raw_coordinate_system: str = "raw_unicode_code_points"


@dataclass(frozen=True)
class EditionNativeDecision:
    dimension: str
    value: str
    proofs: Tuple[EditionNativeSpan, ...] = ()
    reason: str = ""
    dependencies: Tuple[str, ...] = ()
    previous_value: str = ""


@dataclass(frozen=True)
class EditionNativeNP:
    full_np: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    head: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    governed_predicate_ids: Tuple[str, ...] = ()
    status: str = "NOT_OBSERVED"
    reason: str = "parser_did_not_resolve_grammatical_np"


def _edition_native_sources(sources: Tuple[Tuple[str, str], ...]) -> Tuple[EditionNativeSource, ...]:
    result = []
    for index, (role, raw) in enumerate(sources):
        used = unicodedata.normalize("NFKC", raw)
        # A boundary is usable only if normalization on both sides composes
        # exactly to the same whole source. Combined characters are never split.
        if used == raw:
            boundaries = tuple((pos, pos) for pos in range(len(raw) + 1))
        else:
            candidates = {}
            for pos in range(len(raw) + 1):
                left = unicodedata.normalize("NFKC", raw[:pos])
                right = unicodedata.normalize("NFKC", raw[pos:])
                if left + right == used:
                    candidates.setdefault(len(left), []).append(pos)
            boundaries = tuple((u, positions[0]) for u, positions in sorted(candidates.items())
                               if len(positions) == 1)
        result.append(EditionNativeSource(
            f"{role}:{index}", role, index, raw, used,
            hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            hashlib.sha256(used.encode("utf-8")).hexdigest(), boundaries))
    return tuple(result)


@lru_cache(maxsize=1)
def _edition_native_module_sha() -> str:
    with open(__file__, "rb") as source_file:
        return hashlib.sha256(source_file.read()).hexdigest()


def _edition_native_span(sources: Tuple[EditionNativeSource, ...], index: int,
                         span: Tuple[int, int]) -> EditionNativeSpan:
    if not sources or not 0 <= index < len(sources) or len(span) != 2:
        return EditionNativeSpan()
    source = sources[index]
    start, end = span
    if not 0 <= start < end <= len(source.used_text):
        return EditionNativeSpan(source.source_id, index, reason="empty_or_invalid_used_span")
    used_text = source.used_text[start:end]
    mapping = dict(source.boundary_map)
    if start not in mapping or end not in mapping:
        return EditionNativeSpan(source.source_id, index, span, used_text,
                                 reason="raw_boundary_not_exactly_representable")
    raw_span = (mapping[start], mapping[end])
    raw_text = source.raw_text[slice(*raw_span)]
    if unicodedata.normalize("NFKC", raw_text) != used_text:
        return EditionNativeSpan(source.source_id, index, span, used_text,
                                 reason="raw_interval_normalization_not_exact")
    return EditionNativeSpan(source.source_id, index, span, used_text, raw_span, raw_text,
                             "OBSERVED", "exact_normalization_boundary_and_interval")


def _edition_native_np(sources: Tuple[EditionNativeSource, ...], index: int,
                       span: Tuple[int, int], *, marker_span: Tuple[int, int] = ()) -> EditionNativeNP:
    """Select nominal head and grammatical case extent while parsing an object.

    The lexical object locator is a seed, not a fabricated NP or title head.
    Without morphological evidence the grammatical fields remain unobserved.
    """
    if not sources or not span:
        return EditionNativeNP()
    source = sources[index].used_text
    kiwi = _edition_kiwi()
    if kiwi is None:
        return EditionNativeNP(reason="morphological_np_parser_unavailable")
    start, end = span
    try:
        tokens = list(kiwi.tokenize(source[start:end + 8]))
    except Exception:
        return EditionNativeNP(reason="morphological_np_parse_failed")
    nominal = [t for t in tokens if t.tag.startswith("N") and start + t.start < end
               and not (marker_span and marker_span[0] <= start + t.start < marker_span[1])]
    if not nominal:
        return EditionNativeNP(reason="object_seed_has_no_nominal_head")
    head = nominal[-1]
    head_span = (start + head.start, start + head.start + head.len)
    extension = next((t for t in tokens if start + t.start == end
                      and t.tag in {"JKO", "JKS", "JX", "JKG", "JKB"}), None)
    full_end = end + extension.len if extension else end
    # A preceding adnominal clause may enlarge a record/reader NP. Its exact
    # left boundary is not determined by the lexical seed; do not certify it.
    prefix_start = max(source.rfind(".",0,start),source.rfind("\n",0,start)) + 1
    preceding = source[prefix_start:start]
    try:
        unresolved_modifier = any(t.tag=="ETM" for t in kiwi.tokenize(preceding))
    except Exception:
        unresolved_modifier = True
    if unresolved_modifier and not marker_span:
        return EditionNativeNP(head=_edition_native_span(sources,index,head_span),
            reason="preceding_adnominal_modifier_full_np_left_boundary_not_resolved")
    return EditionNativeNP(_edition_native_span(sources, index, (start, full_end)),
                           _edition_native_span(sources, index, head_span),
                           status="OBSERVED", reason="source_nominal_head_and_attached_case_particle")


@dataclass(frozen=True)
class EditionWorkMention:
    """One work surface in the source, independent of the evaluated candidate."""

    mention_id: str
    source_id: str
    source_role: str
    source_index: int
    line_index: int
    paragraph_id: int
    span: Tuple[int, int]
    marker_span: Tuple[int, int]
    work_id: str
    title: str
    marker: str
    native_span: EditionNativeSpan = field(default_factory=EditionNativeSpan)


@dataclass(frozen=True)
class EditionSourceEvent:
    """An event edge to a particular work mention, never a candidate category."""

    event_id: str
    object_mention_id: str
    evidence_span: Tuple[int, int]
    predicate: str
    actor: str
    speaker: str
    modality: str
    stance: str
    supersedes_event_id: Optional[str] = None
    clause_id: str = ""
    evidence_source_id: str = ""
    object_id: str = ""
    time: str = "current"
    edge_kind: str = ""
    predicate_head_span: Tuple[int, int] = ()
    source_proven: bool = False
    supports_publish: bool = True
    native_evidence: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    native_predicate: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    predicate_id: str = ""
    native_trace: Tuple[EditionNativeDecision, ...] = ()
    withdrawal_scope: str = "NOT_OBSERVED"
    withdrawal_target_event_ids: Tuple[str, ...] = ()
    withdrawal_target_object_ids: Tuple[str, ...] = ()
    withdrawal_proof: EditionNativeSpan = field(default_factory=EditionNativeSpan)


@dataclass(frozen=True)
class EditionSourceClause:
    clause_id: str
    source_id: str
    source_index: int
    paragraph_id: int
    span: Tuple[int, int]
    actor: str
    modality: str
    native_span: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    native_trace: Tuple[EditionNativeDecision, ...] = ()


@dataclass(frozen=True)
class EditionSourceObject:
    object_id: str
    source_id: str
    source_index: int
    span: Tuple[int, int]
    kind: str
    mention_id: str = ""
    actor: str = "unknown"
    predicate: str = ""
    modality: str = "unknown"
    owner: str = "unknown"
    parent_object_id: str = ""
    native_span: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    native_np: EditionNativeNP = field(default_factory=EditionNativeNP)
    native_trace: Tuple[EditionNativeDecision, ...] = ()


@dataclass(frozen=True)
class EditionSourcePredicate:
    """A source predicate and its governed arguments, before any candidate query."""

    predicate_id: str
    clause_id: str
    source_id: str
    source_index: int
    head_span: Tuple[int, int]
    scope_span: Tuple[int, int]
    predicate: str
    actor: str
    speaker: str
    modality: str
    stance: str
    object_ids: Tuple[str, ...]
    record_owner: str = "unknown"
    native_full_predicate: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    native_lexical_head: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    native_scope: EditionNativeSpan = field(default_factory=EditionNativeSpan)
    native_trace: Tuple[EditionNativeDecision, ...] = ()


@dataclass(frozen=True)
class EditionSourceLedger:
    work_mentions: Tuple[EditionWorkMention, ...]
    events: Tuple[EditionSourceEvent, ...]
    projections: Tuple[Tuple[str, EditionMarkerMention], ...]
    clauses: Tuple[EditionSourceClause, ...] = ()
    objects: Tuple[EditionSourceObject, ...] = ()
    predicates: Tuple[EditionSourcePredicate, ...] = ()
    legacy_proposals: Tuple[EditionSourceEvent, ...] = ()
    native_sources: Tuple[EditionNativeSource, ...] = ()
    native_reductions: Tuple[Mapping[str, Any], ...] = ()
    native_provenance: Mapping[str, Any] = field(default_factory=dict)
    record_role_provenance: Tuple[RecordRoleProvenanceDraft, ...] = ()
    record_role_lexical_evidence: Tuple[Mapping[str, Any], ...] = ()


def _edition_work_surface_before_marker(
    line: str, marker_start: int, known_headlines: Tuple[str, ...] = (),
) -> Optional[Tuple[int, str]]:
    """Find a full work noun phrase before a marker without a candidate hint."""
    before = line[:marker_start]
    final = re.search(r"(?P<word>[가-힣A-Za-z0-9]+)\s*$", before)
    if not final:
        return None
    start = final.start("word")
    final_word = final.group("word")
    kiwi = _edition_kiwi()
    if kiwi is not None:
        try:
            tokens = kiwi.tokenize(final_word)
            if tokens and tokens[-1].tag in {"JX", "JKS"}:
                final_word = final_word[:-len(tokens[-1].form)]
        except Exception:
            pass
    if final_word == final.group("word") and final_word[-1:] in {"은", "는", "이", "가", "도"}:
        possible = final_word[:-1]
        if any(re.search(r"(?<!\w)" + re.escape(possible) + r"(?!\w)", heading)
               for heading in known_headlines):
            final_word = possible
    # A genitive content noun can be part of a longer title. Source owners,
    # records, and deictic books instead end at the following work surface.
    context_heads = {
        "원글의", "본문의", "글의", "게시글의", "게시물의", "포스트의",
        "책의", "작품의", "소설의", "기록의", "메모의", "독서일지의",
        "독후감의", "감상문의", "내", "제", "나의", "저의", "친구의",
        "책", "작품", "기록", "판본", "표지", "사진", "원문", "서지",
        "친구", "형", "같은", "동일한", "문단", "문장", "반면",
    }
    temporal_heads = {"뒤", "후", "다음", "이후", "어젯밤", "오늘", "어제", "내일",
                      "오전", "오후", "밤", "새벽", "저녁", "점심", "지난달"}
    while True:
        previous = re.search(
            r"(?P<word>[가-힣A-Za-z0-9]+)(?P<gap>\s*[:\-《]\s*|\s+)$",
            before[:start],
        )
        if not previous:
            break
        word = previous.group("word")
        # A possessive record container governs the following work NP; it is
        # not a prefix of that work's name. Resolve this from the owner's
        # grammatical phrase, rather than a list of forbidden title words.
        record_np = re.search(r"(?:내|제|나의|저의|친구(?:의)?|동료(?:의)?|형(?:의)?|동생(?:의)?)\s*(?:독서\s*)?(?:수첩|노트|일지|장|표|기록|메모)(?:의)?\s*$",
                              before[:start])
        result_np = word == "결과" and re.search(
            r"(?:\S+(?:한|된|해|하여)|조사|분석|검증|대조|확인)\s+결과\s*$", before[:start])
        if record_np or result_np:
            break
        temporal_noun = word in {"봄","여름","가을","겨울","월","주","해","날"} and bool(
            re.search(r"(?:지난|다음|올|이번|작년|내년)\s*$",before[:previous.start("word")]))
        if (word in _EDITION_DISCOURSE_ADJUNCTS or
                (word in {"과", "와", "및", "하고", "랑"}
                 and before[:previous.start("word")].rstrip().endswith("]"))):
            break
        if (word in context_heads or (word.endswith("의") and word[:-1] in context_heads)
                or (word.endswith("의") and before[:previous.start("word")].rstrip().endswith("출판사"))
                or (word in temporal_heads and not word.endswith("의")) or temporal_noun):
            break
        if kiwi is None:
            if not word.endswith("의"):
                break
        else:
            try:
                tags = [token.tag for token in kiwi.tokenize(word)]
                context_tokens = kiwi.tokenize(before[max(0, previous.start() - 24):final.end("word")])
            except Exception:
                break
            before_title = [token for token in context_tokens
                            if token.start + token.len <= start - max(0, previous.start() - 24)]
            contextual_adnominal = bool(before_title and before_title[-1].tag == "ETM")
            contextual_verb = any(token.tag.startswith("VV") for token in before_title[-2:])
            if contextual_adnominal and contextual_verb:
                break
            lexical = bool(tags and (
                all(tag in {"NNG", "NNP", "XPN", "MM", "JKG"} for tag in tags)
                or (tags[-1] == "ETM" and tags[0].startswith("VA"))
            ))
            if not lexical:
                break
        start = previous.start("word")
    work = re.sub(r"[:\-《》]", " ", before[start:final.start("word")] + final_word)
    return start, re.sub(r"\s+", " ", work).strip()


def _edition_scan_candidate_mentions_from_sources(
    sources: Iterable[Tuple[str, Any]], candidate_title: str,
    *, allowed_ids: Optional[set[str]] = None,
    collected: Optional[List[Tuple[str, _EditionClaimLedger, int]]] = None,
    source_titles: Optional[Mapping[str, str]] = None,
) -> Tuple[EditionMarkerMention, ...]:
    """Keep source and assertion scope attached to candidate-specific markers.

    A quoted title is reported speech. A local correction denies the edition;
    neither can establish the current work's edition for publication.
    """
    title = unicodedata.normalize("NFKC", str(candidate_title or ""))
    if source_titles is None and not _title_key(_EDITION_MARKER_RE.sub("", title)):
        return ()
    base_surface = re.sub(r"\\\s+", r"\\s+", re.escape(_EDITION_MARKER_RE.sub("", title).strip()))
    mentions: List[EditionMarkerMention] = []
    for source_index, (source_role, value) in enumerate(sources):
        source_role = str(source_role or "unknown")
        source_text = unicodedata.normalize("NFKC", str(value or ""))
        source_lines = source_text.splitlines()
        source_pieces = source_text.splitlines(keepends=True)
        line_offset = 0
        for line_index, line in enumerate(source_lines):
            next_line = source_lines[line_index + 1] if line_index + 1 < len(source_lines) else ""
            line_break_len = len(source_pieces[line_index]) - len(line)
            # An actual empty line creates the paragraph referred to by
            # "위 문단". Preserve the skipped bytes in the evidence span.
            if (not next_line.strip() and line_index + 2 < len(source_lines)
                    and re.match(r"\s*위\s*문단", source_lines[line_index + 2])):
                line_break_len += len(source_pieces[line_index + 1])
                next_line = source_lines[line_index + 2]
            # Quote boundaries are line-local: a different comment or paragraph
            # must never change this mention's speaker or assertion.
            quote_spans = [
                (quote.start(), quote.end())
                for quote in re.finditer(r"'[^']*'|\"[^\"]*\"|“[^”]*”|‘[^’]*’|`[^`]*`", line)
            ]
            for match in _EDITION_MARKER_RE.finditer(line):
                mention_id = f"{source_index}:{line_index}:{match.start()}:{match.end()}"
                if source_titles is not None:
                    if mention_id not in source_titles:
                        continue
                    title = source_titles[mention_id]
                    base_surface = re.sub(r"\\\s+", r"\\s+", re.escape(_EDITION_MARKER_RE.sub("", title).strip()))
                if allowed_ids is not None and mention_id not in allowed_ids:
                    continue
                before, after = line[:match.start()], line[match.end():]
                if source_titles is None and (not _edition_marker_adjacent_to_candidate(before, after, title)
                        and not (allowed_ids is not None
                                 and _edition_modifier_context_before_title(before, title))):
                    continue
                quoted = any(start <= match.start() < end for start, end in quote_spans)
                # A closing quote belongs to the mention, not to its polarity.
                clause_end = _edition_claim_clause(line, match.end())[1]
                following = (
                    line[match.end():clause_end] if source_role == "post_body" else after[:80]
                ).lstrip(" \t'\"”’`")
                denied = bool(_EDITION_DENIAL_RE.match(following))
                if re.match(
                    r"^[을를]\s*읽(?:은|었다는)\s*(?:게|건)\s*아니",
                    following,
                ):
                    denied = True
                if re.match(r"^(?:이라고|라고)\s*했", following) and _REPORTED_DENIAL_RE.search(following):
                    denied = True
                correction = re.search(
                    r"(?:보였|생각했|줄\s*알았|기억.{0,12}(?:틀리|틀렸)|"
                    r"맞나\s*싶었|착각(?:했|해서|하)|오해했|잘못\s*알았|"
                    r"믿(?:었|고\s*있었)|오보다|틀렸|틀리|정정|"
                    r"(?:기억했|적었)(?:지만|으나|는데)|"
                    r"읽었다는\s*건\s*아니)",
                    following,
                )
                revised_edition = bool(correction and any(
                    other.casefold() != match.group(1).casefold()
                    for other in re.findall(
                        r"(?:단행본|연재본|개정판|합본|특별판|완전판|전자책|이북|ebook|e북)",
                        following[correction.start():], flags=re.IGNORECASE,
                    )
                ))
                if revised_edition:
                    denied = True
                reported = quoted and source_role != "post_title" and (
                    bool(_REPORTED_CLAIM_RE.match(following))
                    or not _DIRECT_EDITION_USE_RE.search(following[:40])
                )
                # Bind an experience or claim to the topic/subject immediately
                # before the work title. A third-person subject is not the
                # post author's current edition; first person and time topics
                # keep the author's own reading in scope.
                local_prefix = re.split(
                    r"[.!?。\n]\s*|\S+(?:고|며|지만|는데|다가|더니)\s+"
                    r"|(?<=[다요음고데지네])\s*,\s*", before,
                )[-1]
                local_prefix = re.sub(base_surface + r"(?:은|는|이|가|도)?\s*$", "", local_prefix)
                subjects = list(re.finditer(
                    r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가도](?=[,\s]|$)",
                    local_prefix,
                ))
                # Korean adnominal verbs such as "내가 읽은/좋아하는 작품" end
                # in the same syllables as topic particles; they are not a
                # newer subject than the explicit first-person pronoun.
                subject = next((item for item in reversed(subjects) if not re.search(
                    r"(?:읽|좋아하|좋|산|본|보|고르|찾|추천하|추천|사랑하|사랑)$", item.group(1)
                )), None)
                # In "friend read [the book I recommended]", the first
                # subject governs reading; the nearer one belongs to the
                # relative clause describing the book.
                adnominal_relation = bool(re.search(
                    r"(?:[가-힣]*(?:던|은|한|넨|는|준|본)|산)\s*$",
                    local_prefix,
                ))
                if adnominal_relation and len(subjects) > 1:
                    subject = subjects[0]
                self_relative_reading = bool(re.search(
                    r"(?:^|\s)(?:내가|나는|제가|저는)\s+"
                    r"(?:\S+\s+){0,4}(?:읽은|읽었던|본)\s*$",
                    local_prefix,
                ))
                title_is_subject = bool(re.search(
                    base_surface + r"(?:은|는|이|가|도)\s*$", local_prefix,
                ))
                other_account = bool(
                    subject
                    and not title_is_subject
                    and not re.fullmatch(
                        r"(?:오늘|어제|내일|오전|오후|밤|새벽|점심|저녁)(?:에)?",
                        subject.group(1),
                    )
                    and subject.group(1) not in {
                        "나", "내", "저", "제", "우리", "저희",
                        "오늘", "어제", "내일", "요즘", "최근", "이번", "지금", "방금",
                        "작품", "소설", "글", "본문", "게시글", "제목", "이야기", "내용",
                    }
                )
                if other_account:
                    reported = True
                if subject and subject.group(1) in {"책", "판본"} and _edition_current_book_target(local_prefix):
                    other_account = False
                    reported = quoted and source_role != "post_title"
                other_possessor = re.search(
                    r"(?:^|\s)([가-힣A-Za-z]{1,20})(?:의\s+|\s+)"
                    r"[가-힣A-Za-z]{1,20}(?:에|에서)\s*$",
                    local_prefix,
                )
                if other_possessor and other_possessor.group(1) not in {
                    "나", "내", "저", "제", "우리", "저희", "글", "본문", "원글",
                    "오늘", "어제", "내일", "요즘", "최근", "이번", "지금", "방금",
                }:
                    other_account = True
                    reported = True
                # A third party's shelf locates the book, but an ensuing
                # extraction and reading describes the author's own use.
                if other_possessor and re.match(
                    r"^[을를]?\s*(?:꺼내|찾아)\s*읽", following,
                ):
                    other_account = False
                    reported = False
                if (
                    subject and subject.group(1) in {"나", "내", "저", "제"}
                    and re.match(r"^\s*[을를]\s*(?:읽|봤|정주행)", following)
                ):
                    other_account = False
                    reported = False
                author_reads_transferred_copy = bool(
                    re.search(
                        r"(?:가|는|은)\s+(?:빌려\s*준|읽던|추천한|건넨|선물한|사준)\s*$",
                        local_prefix,
                    )
                    and not (
                        len(subjects) > 1 and subject
                        and subject.group(1) not in {"나", "내", "저", "제", "우리", "저희"}
                    )
                    and re.match(
                        r"^\s*[을를]\s*(?:(?:오늘부터|어제부터|내가|나는|제가|저는)\s*){0,2}"
                        r"(?:읽|정주행|봤)",
                        following,
                    )
                    and not re.match(r"^\s*[을를]\s*읽은\s*건\s*", following)
                    and not re.search(
                        r"(?:안|못)\s*(?:읽|정주행|봤)|"
                        r"(?:읽|정주행|보)(?:는|은|었다는)?\s*건\s*아니",
                        following[:50],
                    )
                )
                if author_reads_transferred_copy:
                    other_account = False
                    reported = False
                if self_relative_reading:
                    # A friend may be the main-clause reader, but the author
                    # explicitly says they read or saw this same copy too.
                    other_account = False
                    reported = False
                if source_role == "comment" and _edition_current_book_target(local_prefix):
                    # "원글에서 읽은 책" is the object of the reply's check,
                    # not a new third-person commenter account.
                    other_account = False
                    reported = quoted
                nominal_reader = re.match(
                    r"^\s*[을를]\s*읽은\s*건\s+([가-힣A-Za-z]{1,20}?)(?:[이가은는]|다|였다|아니다)",
                    following,
                )
                if nominal_reader:
                    reader_is_author = nominal_reader.group(1) in {
                        "나", "내", "저", "제", "우리", "저희",
                    }
                    reader_denied = bool(re.search(r"\b아니(?:다|었)", following))
                    other_account = not reader_is_author
                    reported = not reader_is_author
                    denied = denied or reader_denied
                object_reader = re.match(
                    r"^\s*[을를]\s*([가-힣A-Za-z]{1,20}?)[은는이가]\s+"
                    r"(?:읽|봤|정주행)",
                    following,
                )
                if object_reader:
                    reader_is_author = object_reader.group(1) in {
                        "나", "내", "저", "제", "우리", "저희",
                    }
                    other_account = not reader_is_author
                    reported = not reader_is_author
                postposed_speaker = re.search(
                    r"(?:이?라고|다고)\s+([가-힣A-Za-z]{1,20}?)[은는이가도]"
                    r"\s+.{0,30}(?:말|하|주장)", following,
                )
                if postposed_speaker and postposed_speaker.group(1) not in {
                    "나", "내", "저", "제", "우리", "저희",
                }:
                    reported = True
                    other_account = True
                self_subject = bool(subject and subject.group(1) in {
                    "나", "내", "저", "제", "우리", "저희",
                })
                self_postposed = bool(postposed_speaker and postposed_speaker.group(1) in {
                    "나", "내", "저", "제", "우리", "저희",
                })
                direct_self_confirmation = bool(re.fullmatch(
                    r"(?:[이가은는]\s*)?맞다고\s*(?:(?:내가|제가)\s*)?"
                    r"(?:직접\s*)?(?:확인|검증)(?:함|했(?:습니다|어요|다))\s*[.!。!]*",
                    following.strip(),
                ) or re.fullmatch(
                    r"(?:이?라고|라고)\s*(?:(?:내가|제가|나는|저는)\s*)?"
                    r"직접\s*(?:확인|검증)(?:함|했(?:습니다|어요|다))\s*[.!。!]*",
                    following.strip(),
                ) or re.fullmatch(
                    r"(?:이?라고|라고)\s*(?:(?:방금|오늘|어제|지금)\s*)?"
                    r"(?:내가|제가|나는|저는)\s*직접\s*(?:확인|검증)"
                    r"(?:함|했(?:습니다|어요|다))\s*[.!。!]*",
                    following.strip(),
                ) or re.fullmatch(
                    r"(?:이?라고|라고)\s*"
                    r"(?:(?:오늘|어제|방금|지금)\s*)?"
                    r"(?:내가|제가|나는|저는)\s*"
                    r"(?:(?:오늘|어제|방금|지금)\s*)?"
                    r"(?:판본을\s*)?(?:직접\s*)?"
                    r"(?:확인|검증)(?:함|했(?:습니다|어요|다))\s*[.!。!]*",
                    following.strip(),
                ))
                # In an author's direct identification, "this book" is the
                # identified object, not a third-party speaker. A named
                # earlier actor still controls the utterance.
                deictic_object = re.search(
                    r"(?:^|\s)이\s+(?:책|작품|소설)[은는이가]\s*$",
                    local_prefix,
                )
                if source_role == "post_body" and deictic_object and not direct_self_confirmation:
                    actor_prefix = local_prefix[:deictic_object.start()]
                    direct_self_confirmation = bool(
                        _edition_subject_actor(actor_prefix) == "author"
                        and re.fullmatch(
                            r"(?:이?라고|라고)\s*(?:확인|검증)"
                            r"(?:함|했(?:습니다|어요|다))\s*[.!。!]*",
                            following.strip(),
                        )
                    )
                if source_role == "post_body" and direct_self_confirmation and deictic_object:
                    actor_prefix = local_prefix[:deictic_object.start()]
                    actor = _edition_subject_actor(actor_prefix)
                    if actor in {"author", "implicit"}:
                        other_account = False
                        reported = quoted and source_role != "post_title"
                    else:
                        other_account = True
                        reported = True
                hearsay = bool(re.search(
                    r"(?:다고|라고).{0,20}(?:들었|전해|하더라|하던데|말하|했다)|"
                    r"(?:들었|전해|하더라|하던데|다더라|소문)", following,
                )) and not (
                    ((self_subject or self_postposed) and not other_account)
                    or direct_self_confirmation
                    or (object_reader and not other_account)
                )
                if hearsay:
                    reported = True
                # A commenter's reading or ownership is a separate account.
                # Only a reply explicitly identifying this post's edition, or
                # established direct quoted commentary, can supply the marker.
                if source_role == "comment":
                    references_post = bool(re.search(
                        r"(?:이|그|해당|내|제|우리)\s*"
                        r"(?:글|게시글|게시물|포스트|본문|작품)|"
                        r"본문(?:의|에서)?|원글|글쓴이|이거|여기서",
                        local_prefix,
                    )) and not _edition_other_comment_document(local_prefix)
                    reported_intro = bool(re.search(
                        r"(?:말로|한테\s*들었|에게\s*들었|들었는데)", before,
                    ))
                    confirmer_before_post = re.search(
                        r"(?:^|\s)([가-힣A-Za-z]{1,20}?)[은는이가]\s+"
                        r"(?:확인|검증)했는데\s+(?:(?:이|그|해당|내|제)\s*"
                        r"(?:글|게시글|게시물|포스트|본문)|원글|본문)",
                        before,
                    )
                    if confirmer_before_post and confirmer_before_post.group(1) not in {
                        "나", "내", "저", "제", "우리", "저희",
                    }:
                        reported_intro = True
                    identification_text = following.strip()
                    separate_account = re.fullmatch(
                        r"(.+?),\s*([가-힣A-Za-z]{1,20})\s+것[은는]\s+"
                        r"(?:단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)"
                        r"(?:이다|입니다|임|이야)?\s*[.!。!]*",
                        identification_text,
                    )
                    if separate_account and separate_account.group(2) not in {
                        "이", "그", "해당", "본문", "원글", "글", "내", "나", "제", "저",
                    }:
                        identification_text = separate_account.group(1).strip()
                    terminal_identification = bool(direct_self_confirmation or (
                        _edition_current_book_target(local_prefix)
                        and _edition_completed_identification(identification_text)
                    ) or re.fullmatch(
                        r"(?:판본|표기)(?:을|를)\s*(?:제가|내가|저는|나는)\s*"
                        r"직접\s*(?:확인|검증)(?:했(?:습니다|어요|다)|함)\s*[.!。!]*",
                        identification_text,
                    ) or re.fullmatch(
                        r"(?:표기|판본)(?:는|가|도)?\s*"
                        r"(?:맞다|맞습니다|맞음|맞아요|확실하다|확실함)\s*[.!。!]*",
                        identification_text,
                    ) or re.fullmatch(
                        r"(?:[이가은는]\s*)?(?:맞음|맞다|맞습니다|맞아|이다|입니다|이야|임|"
                        r"맞아요|맞다고\s*(?:(?:내가|제가)\s*)?"
                        r"(?:직접\s*)?(?:확인|검증)(?:함|했(?:습니다|어요|다))|"
                        r"확실함|확실하다|확실합니다|확실해|확실해요|"
                        r"아니다|아니야|아니에요|아님|아니지|아니라)\s*[.!。!]*",
                        identification_text,
                    ) or re.fullmatch(
                        r"(?:[이가은는]\s*)?맞음\s*[.!。!]\s*확인(?:함|했다|했습니다)\s*[.!。!]*",
                        identification_text,
                    ) or re.fullmatch(
                        r"(?:[이가은는]\s*)?맞음\s*,\s*(?:내가|제가)\s+"
                        r"확인(?:함|했다|했습니다|했어요)\s*[.!。!]*",
                        identification_text,
                    ))
                    direct_post_denial = bool(_EDITION_DENIAL_RE.match(following))
                    speculative_claim = bool(re.search(
                        r"(?:추측|짐작|가능성|것\s*같|듯|모르)", following,
                    ))
                    commenters_own_post = bool(re.search(
                        r"(?:^|[\s'\"“‘`])(?:내|제|우리)\s*"
                        r"(?:글|게시글|게시물|포스트|본문)(?:의|에서\s*(?:다룬|말한))\s*$",
                        local_prefix,
                    ))
                    identifies_post = bool(
                        references_post and (terminal_identification or direct_post_denial)
                        and not (
                            other_account or hearsay or reported_intro
                            or commenters_own_post or speculative_claim
                        )
                    )
                    if identifies_post:
                        # Quotation marks around the work name do not turn a
                        # direct, post-bound identification into hearsay.
                        reported = False
                    direct_quoted_commentary = bool(
                        quoted and _DIRECT_EDITION_USE_RE.search(following[:40]) and not reported
                    )
                    if not (identifies_post or direct_quoted_commentary):
                        reported = True
                if source_role == "comment" and re.search(r"(?:친구|동료)\s+글에서\s+말한\s*$",local_prefix):
                    continue
                modality = _edition_statement_modality(line, match)
                events = _edition_claim_events(
                    line, match, source_role, local_prefix, next_line, line_break_len,
                )
                reading_negated = bool(re.search(
                    r"(?:(?:안|못)\s*(?:읽|보|펼치|정주행|완독|재독)|"
                    r"(?:읽|보|펼치|정주행|완독|재독)\s*지\s*(?:않|못))",
                    following[:55],
                ))
                if source_role == "post_body" and reading_negated and not other_account:
                    events = tuple(event for event in events
                                   if not (event.predicate == "read" and event.stance == "asserted"))
                    events = (*events, EditionClaimEvent(
                        marker_span=(match.start(), match.end()),
                        evidence_span=(match.start(), clause_end),
                        clause_role="main", actor="author", predicate="read",
                        stance="denied", current_post_relation=True,
                    ))
                if modality != "direct":
                    events = tuple(
                        replace(event, stance="reported", current_post_relation=False,
                                modality=modality)
                        if event.stance == "asserted" else event
                        for event in events
                    )
                if source_role == "comment" and (
                    other_account or hearsay or reported_intro or commenters_own_post
                    or _edition_other_comment_document(local_prefix)
                    or speculative_claim
                    or re.search(r"(?:^|\s)(?:아마|아마도|추측컨대)\s+", before)
                ):
                    events = tuple(event for event in events if event.clause_role != "comment")
                events = _edition_projection_event(
                    line, match, source_role, following, events,
                    denied=denied, reported=reported, other_account=other_account,
                    hearsay=hearsay, identifies_post=identifies_post if source_role == "comment" else False,
                    quoted=quoted, author_subject=self_subject,
                    transferred_read=author_reads_transferred_copy,
                    direct_identification=direct_self_confirmation,
                    modality=modality,
                )
                claim = _edition_claim_ledger(
                    line, match, source_role, source_index, line_index,
                    _title_key(title), events, quoted,
                )
                if collected is not None:
                    collected.append((mention_id, claim, line_offset))
                # Projection has one authority: the reduced event ledger.
                # In particular, an eventless fallback cannot borrow the
                # old surface booleans' implicit publication permission.
                current_relation = claim.status in {"asserted", "denied"} and claim.target_relation == "bound"
                decisive = next((
                    event for event in reversed(claim.events)
                    if event.stance in {"asserted", "denied"} and event.current_post_relation
                ), None)
                basis = (
                    "author_read" if decisive and decisive.predicate == "read" else
                    "current_post_record" if decisive and decisive.predicate == "record" else
                    "bound_comment_identify" if decisive and source_role == "comment" else
                    "author_identify" if decisive else ""
                )
                mentions.append(EditionMarkerMention(
                    candidate_title=title,
                    marker=match.group(1).casefold(),
                    source_role=source_role,
                    source_index=source_index,
                    polarity="denied" if claim.status == "denied" and current_relation
                    else "asserted" if claim.status == "asserted" and current_relation
                    else "reported",
                    quoted=quoted,
                    current_post_relation=current_relation,
                    claim_status=claim.status,
                    reader_actor=claim.reader_actor,
                    basis=basis,
                    evidence_span=tuple(
                        line_offset + position for position in (
                            decisive.evidence_span if decisive else (match.start(), match.end())
                        )
                    ),
                    pending=any(edge.kind == "pending_verification" for edge in claim.edges),
                ))
            line_offset += len(source_pieces[line_index])
    return tuple(mentions)


@lru_cache(maxsize=256)
def _edition_build_source_ledger(
    sources: Tuple[Tuple[str, str], ...],
    native_sources: Tuple[EditionNativeSource, ...] = (),
) -> EditionSourceLedger:
    """Parse source works and their events once for every candidate in a post."""
    work_mentions: List[EditionWorkMention] = []
    known_headlines = tuple(text for role, text in sources if role == "post_title")
    for source_index, (source_role, source_text) in enumerate(sources):
        pieces = source_text.splitlines(keepends=True)
        paragraph_id = 0
        line_offset = 0
        for line_index, piece in enumerate(pieces):
            line = piece.rstrip("\r\n")
            if not line.strip():
                paragraph_id += 1
                line_offset += len(piece)
                continue
            for marker_match in _EDITION_MARKER_RE.finditer(line):
                surface = _edition_work_surface_before_marker(
                    line, marker_match.start(), known_headlines,
                )
                if surface is None:
                    continue
                title_start, work = surface
                marker = marker_match.group(1).casefold()
                title = f"{work} [{marker}]"
                mention_id = (
                    f"{source_index}:{line_index}:{marker_match.start()}:{marker_match.end()}"
                )
                work_mentions.append(EditionWorkMention(
                    mention_id=mention_id, source_id=f"{source_role}:{source_index}",
                    source_role=source_role, source_index=source_index,
                    line_index=line_index, paragraph_id=paragraph_id,
                    span=(line_offset + title_start, line_offset + marker_match.end()),
                    marker_span=(line_offset + marker_match.start(),
                                 line_offset + marker_match.end()),
                    work_id=_title_key(work), title=title, marker=marker,
                    native_span=_edition_native_span(native_sources, source_index,
                        (line_offset + title_start, line_offset + marker_match.end())),
                ))
            line_offset += len(piece)

    projections: List[Tuple[str, EditionMarkerMention]] = []
    events: List[EditionSourceEvent] = []
    collected: List[Tuple[str, _EditionClaimLedger, int]] = []
    scanned = _edition_scan_candidate_mentions_from_sources(
        sources, "", source_titles={item.mention_id: item.title for item in work_mentions},
        collected=collected,
    )
    for (mention_id, claim, line_offset), projection in zip(collected, scanned):
        projections.append((mention_id, projection))
        base_id = f"{mention_id}:claim"
        prior_id = base_id
        events.append(EditionSourceEvent(
            event_id=base_id, object_mention_id=mention_id,
            evidence_span=(line_offset + claim.claim_key[-1][0],
                           line_offset + claim.claim_key[-1][1]),
            predicate="claim", actor="unknown", speaker=claim.speaker_actor,
            modality=claim.modality, stance="unresolved",
        ))
        for ordinal, event in enumerate(claim.events):
            event_id = f"{mention_id}:{ordinal}"
            events.append(EditionSourceEvent(
                event_id=event_id, object_mention_id=mention_id,
                evidence_span=tuple(line_offset + pos for pos in event.evidence_span),
                predicate=event.predicate, actor=event.actor,
                speaker=claim.speaker_actor, modality=event.modality,
                stance=event.stance,
                supersedes_event_id=(prior_id if event.clause_role == "correction" else None),
            ))
            if event.stance in {"asserted", "reported", "unresolved"}:
                prior_id = event_id

    return _edition_bind_source_propositions(sources, tuple(work_mentions), tuple(events), tuple(projections), native_sources)




def _edition_proposition_actor(fragment: str, selected: Optional[List[Tuple[int, int, str]]] = None) -> str:
    subjects = list(re.finditer(
        r"(?:^|\s)(?P<who>나|내|저|제|우리|저희|친구|동료|형|누나|동생|민수|민지)[은는이가도만](?=\s)", fragment))
    if subjects:
        governing = subjects[0] if len(subjects)>1 and re.search(r"(?:은|한|본|던|는)\s*$",fragment) else subjects[-1]
        if selected is not None:
            selected.append((governing.start("who"), governing.end(), "explicit_subject_particle"))
        return "author" if governing.group("who") in {"나","내","저","제","우리","저희"} else "other"
    kiwi = _edition_kiwi()
    if kiwi is not None:
        try:
            tokens = kiwi.tokenize(fragment)
            human = [tokens[i-1].form for i,t in enumerate(tokens) if i and
                     (t.tag=="JKS" or t.tag=="JX" and t.form in {"은","는","도","만"})
                     and (tokens[i-1].tag=="NP" or tokens[i-1].form in
                          {"친구","동료","형","누나","동생"})]
            if human:
                if selected is not None:
                    i = next(i for i in reversed(range(1, len(tokens))) if tokens[i-1].form == human[-1]
                             and tokens[i].tag in {"JKS", "JX"})
                    selected.append((tokens[i-1].start, tokens[i].start + tokens[i].len,
                                     "morphological_subject_particle"))
                return "author" if human[-1] in {"나","내","저","제","우리","저희"} else "other"
        except Exception:
            pass
    return "implicit"


def _edition_source_clauses(sources: Tuple[Tuple[str, str], ...],
                            native_sources: Tuple[EditionNativeSource, ...] = ()) -> Tuple[EditionSourceClause, ...]:
    """Predicate scopes are source objects; candidate titles do not determine them."""
    clauses = []
    for source_index, (role, text) in enumerate(sources):
        boundaries = {0, len(text)}
        quote_spans = [(q.start(), q.end()) for q in re.finditer(r"'[^']*'|\"[^\"]*\"|“[^”]*”|‘[^’]*’", text)]
        for stop in re.finditer(r"[.!?。\n]+\s*", text):
            if not any(a < stop.start() < b for a, b in quote_spans):
                boundaries.add(stop.end())
        for separator in re.finditer(r"[,，:：—–]\s*(?=.{0,20}(?:나는|내가|저는|제가|친구[가는]|동료[가는]|사촌[은이]|형[은이]|동생[은이])\s)",text):
            if not any(a<separator.start()<b for a,b in quote_spans):
                boundaries.add(separator.end())
        # Coordinating/subordinate clauses with their own subject have distinct
        # actors. The connective belongs to the preceding predicate scope.
        for connective in re.finditer(
            r"(?:동안|반면|때|지만|으나|는데|(?<![다라])고|며)\s*[,，]?\s+"
            r"(?=(?:나는|내가|저는|제가|친구[가는]|동료[가는]|형[은이]|동생[은이])\s)", text,
        ):
            boundaries.add(connective.end())
        points = sorted(boundaries)
        for start, end in zip(points, points[1:]):
            chunk = text[start:end]
            if not chunk.strip():
                continue
            actor_spans = []
            actor = _edition_proposition_actor(chunk, actor_spans)
            if actor == "implicit":
                actor = "commenter" if role == "comment" else "author"
            elif role == "comment" and actor == "author":
                actor = "commenter"
            modality = "future" if re.search(
                r"(?:읽(?:을|으려|으려고|겠)|완독(?:하려|할|하겠)|정주행(?:하려|할)|재독(?:하려|할))", chunk,
            ) else "direct"
            clauses.append(EditionSourceClause(
                f"{source_index}:clause:{start}:{end}", f"{role}:{source_index}",
                source_index, len(re.findall(r"\n\s*\n", text[:start])), (start, end), actor, modality,
                native_span=_edition_native_span(native_sources, source_index, (start, end)),
                native_trace=(EditionNativeDecision("actor", actor,
                    tuple(_edition_native_span(native_sources, source_index, (start+a, start+b))
                          for a,b,_ in actor_spans),
                    actor_spans[-1][2] if actor_spans else "implicit_subject_resolved_from_source_role"),
                    EditionNativeDecision("speaker", "commenter" if role == "comment" else "author",
                                          reason="source_role_attribution_without_explicit_speaker_np")),
            ))
    return tuple(clauses)


def _edition_source_predicates(
    sources: Tuple[Tuple[str, str], ...], mentions: Tuple[EditionWorkMention, ...],
    clauses: Tuple[EditionSourceClause, ...], objects: Tuple[EditionSourceObject, ...],
    native_sources: Tuple[EditionNativeSource, ...] = (),
    record_role_evidence: Optional[List[Mapping[str, Any]]] = None,
) -> Tuple[EditionSourcePredicate, ...]:
    """Resolve the arguments of source verbs, independently of legacy proposals.

    A work observation, a quoted record and an actual reading are different
    propositions even when a downstream recognizer labels all three as read.
    Korean ending and particle coordinates govern the actor and object scope.
    """
    kiwi = _edition_kiwi()
    if kiwi is None:
        fallback=[]
        for clause in clauses:
            role,source=sources[clause.source_index]
            fragment=source[slice(*clause.span)]
            for target in [m for m in mentions if m.source_index==clause.source_index and clause.span[0]<=m.span[0]<clause.span[1]]:
                offset=target.marker_span[1]-clause.span[0]
                assertion=re.search(r"맞음|맞(?:다|습니다|아요)|확실(?:함|해요)|단언(?:함|했다)|아님",fragment[offset:])
                if assertion and role=="comment" and not re.search(r"친구|동료|들었|전언|소문|예정|모르|추측|[?？]",fragment):
                    position=target.marker_span[1]+assertion.start()
                    fallback.append(EditionSourcePredicate(f"{clause.clause_id}:literal_assert:{position}",
                        clause.clause_id,clause.source_id,clause.source_index,(position,position+len(assertion.group())),
                        clause.span,"assert","commenter","commenter","direct","asserted",(target.mention_id,)))
            for verb in re.finditer(r"읽(?:었다고|었다|었|습니다|은)|(?:완독|재독|정주행)(?:했다|했습니다)|본(?=\s*사람)",fragment):
                position=clause.span[0]+verb.start()
                local=[m for m in mentions if m.source_index==clause.source_index
                       and clause.span[0]<=m.marker_span[1]<=position]
                nominal=bool(re.search(r"(?:읽은|본)\s*(?:사람|독자)은\s*(?:나|저|내|제)(?:라고|가\s*맞다고)\s*(?:(?:제가|내가|어젯밤|오늘)\s*)?직접\s*확인",fragment))
                if not local or re.search(r"친구|동료|형|동생|소문|전언|아니|없|['\"“‘]",fragment) or re.search(r"사람|독자",fragment) and not nominal:
                    continue
                modality="reported" if verb.group().endswith("다고") else "direct"
                if modality=="reported" and re.search(r"(?:나는|내가|저는|제가)(?:\s|,)",fragment[:verb.start()]) and re.match(r"\s*했다",fragment[verb.end():]):
                    modality="direct"
                actor="commenter" if role=="comment" else "author"
                fallback.append(EditionSourcePredicate(
                    f"{clause.clause_id}:literal:{verb.start()}",clause.clause_id,clause.source_id,
                    clause.source_index,(position,clause.span[0]+verb.end()),clause.span,
                    "read",actor,actor,modality,"asserted" if modality=="direct" else "reported",
                    (local[-1].mention_id,)))
        return tuple(replace(p,
            native_full_predicate=_edition_native_span(native_sources,p.source_index,p.head_span),
            native_scope=_edition_native_span(native_sources,p.source_index,p.scope_span),
            native_trace=(EditionNativeDecision("actor",p.actor,reason="literal_fallback_without_independent_actor_np"),
                EditionNativeDecision("reader","NOT_OBSERVED",reason="literal_fallback_without_reader_np"),
                EditionNativeDecision("modality",p.modality,
                    (_edition_native_span(native_sources,p.source_index,p.head_span),),"literal_fallback_rule"),
                EditionNativeDecision("stance",p.stance,
                    (_edition_native_span(native_sources,p.source_index,p.scope_span),),"literal_fallback_rule"),
                EditionNativeDecision("tense","NOT_OBSERVED",reason="morphology_unavailable"))) for p in fallback)
    predicates: List[EditionSourcePredicate] = []
    self_forms = {"나", "내", "저", "제", "우리", "저희"}
    human_forms = self_forms | {"친구", "동료", "형", "누나", "동생", "민수", "민지",
                               "사촌","선배","후배","어머니","아버지","엄마","아빠","언니","오빠",
                               "고모","이모","삼촌","이웃","할머니","할아버지"}
    record_forms = {"메모", "기록", "노트", "수첩", "독서장", "독서표", "독서일지", "독후감", "감상문", "주장", "후기", "말", "소식"}
    lexical_heads = {"확인": "confirm", "검증": "confirm", "대조": "confirm", "비교":"confirm", "확정":"confirm", "승인": "confirm",
                     "정정": "correct", "수정": "correct", "취소": "withdraw", "철회": "withdraw",
                     "유지": "maintain", "기록": "record_assert", "메모":"record_assert", "기재":"record_assert",
                     "기억":"record_assert", "단언":"assert", "확신":"assert", "확실":"assert", "추천":"publication_assert", "주장":"speech"}
    for clause in clauses:
        role, source = sources[clause.source_index]
        text = source[slice(*clause.span)]
        try:
            tokens = list(kiwi.tokenize(text))
        except Exception:
            continue
        quote_spans = [(q.start(), q.end()) for q in re.finditer(r"'[^']*'|\"[^\"]*\"|“[^”]*”|‘[^’]*’", text)]
        local_mentions = [m for m in mentions if m.source_index == clause.source_index
                          and clause.span[0] <= m.marker_span[0] < clause.span[1]]
        local_objects = [o for o in objects if o.source_index == clause.source_index
                         and clause.span[0] <= o.span[0] < clause.span[1]]
        subjects = []
        for i, token in enumerate(tokens[:-1]):
            particle = tokens[i+1]
            absolute = clause.span[0]+token.start
            if (token.form in human_forms and particle.tag in {"JKS", "JX"}
                    and particle.form in {"이", "가", "은", "는", "도", "만"}
                    and not any(m.span[0] <= absolute < m.span[1] for m in local_mentions)):
                subjects.append((token.start, "author" if token.form in self_forms else "other"))
        heads = []
        record_modes = {}
        nominal_head_starts=set()
        for i, token in enumerate(tokens):
            absolute_token=clause.span[0]+token.start
            if any(m.span[0]<=absolute_token<m.marker_span[1] for m in local_mentions):
                continue
            kind = ""
            head_start = token.start
            if token.tag.startswith("VV"):
                if token.form == "읽":
                    kind = "read"
                elif token.form == "끝내" and any(t.form in {"장", "쪽", "페이지", "권"} for t in tokens[max(0,i-5):i]):
                    kind = "read"
                elif token.form == "보":
                    before = text[max(0,token.start-30):token.start]
                    named_object=bool(local_mentions) and (any(m.marker_span[1]<=clause.span[0]+token.start for m in local_mentions)
                        or any(t.tag=="ETM" for t in tokens[i+1:i+4]))
                    object_particles=any(t.tag=="JKO" for t in tokens[:i])
                    relative_book=any(t.tag=="ETM" for t in tokens[i+1:i+4])
                    if (named_object and (object_particles or relative_book) or re.search(r"(?:끝|마지막|처음).*(?:까지|부터)|(?:본문|원문)(?:을|를)",before)) and not re.search(r"표지|제목|사진",before):
                        kind = "read"
                elif token.form in {"고치","바꾸"}:
                    kind = "correct"
                elif token.form == "거두":
                    kind = "withdraw"
                elif token.form in {"적","쓰"}:
                    kind = "record_assert"
                elif token.form=="바로잡":
                    kind="correct"
                elif token.form=="잡" and i and tokens[i-1].form=="바로":
                    kind="correct"
                elif token.form in {"말하","밝히","인정하","듣","들","전하"}:
                    kind="speech" if token.form not in {"듣","들","전하"} else "hearsay"
                elif token.form=="하" and any(t.tag=="EC" and t.form in {"다고","라고"} for t in tokens[max(0,i-5):i]):
                    kind="speech"
                elif token.form in {"틀리", "맞"}:
                    kind = "assert"
                elif token.form == "맞추":
                    kind = "confirm"
                elif token.form in {"추천","추천하"}:
                    kind = "publication_assert"
                elif token.form == "알" and re.search(r"(?:이|그)\s*책",text[:token.start]):
                    kind = "identify"
                elif token.form == "되" and any(t.form=="잘못" for t in tokens[max(0,i-2):i]):
                    kind = "assert"
            if token.tag == "NNG" and token.form in lexical_heads and any(t.tag in {"XSV","XSA"} for t in tokens[i+1:i+3]):
                kind = lexical_heads[token.form]
            if token.form in {"말","인정"} and any(t.tag=="XSV" for t in tokens[i+1:i+3]):
                kind="speech"
            if token.form == "사실" and any(t.tag == "VCP" for t in tokens[i+1:i+3]):
                kind = "assert"
            if token.form in {"오류","착오","실수"} and any(t.tag=="VCP" for t in tokens[i+1:i+3]):
                kind = "assert"
            if token.form=="되" and token.tag=="XSV" and i and tokens[i-1].form=="잘못":
                kind="assert"
            if token.form in {"맞음","아님"} and token.tag.startswith("N"):
                kind="assert"
            if token.tag.startswith("VA") and token.form in {"재밌","재미있","확실","확실하"}:
                kind="publication_assert" if not token.form.startswith("확실") else "assert"
            if token.form=="확실" and token.tag=="XR" and any(t.tag=="XSA" for t in tokens[i+1:i+3]):
                kind="assert"
            if token.form in {"감상","출간"} and token.tag=="NNG" and local_mentions:
                kind="publication_assert"
            if token.tag == "VCN" and token.form == "아니":
                kind = "assert"
            if token.tag == "VCP" and local_mentions:
                adjacent = [m for m in local_mentions if m.marker_span[1] <= clause.span[0]+token.start
                            and re.fullmatch(r"(?:이|은|는)?\s*",source[m.marker_span[1]:clause.span[0]+token.start])]
                if adjacent:
                    kind = "identify"
            if token.tag=="VCP" and i and tokens[i-1].form in {"단행본","연재본","판본"} and not any(
                    m.span[0]<=clause.span[0]+token.start<m.span[1] for m in local_mentions):
                kind="assert"
            if token.tag in {"XSV","XSA"} or token.tag=="MM" and token.form=="한":
                before = text[max(0,token.start-8):token.start]
                compound = re.search(r"(?:완독|재독|정주행)\s*$", before)
                if compound:
                    kind = "read"
                    head_start = max(0,token.start-8)+compound.start()
            nominal_surface = re.match(r"(?:완독|재독|정주행)(?=\s|[이은을와과,.!?]|$)",text[token.start:]) if token.tag.startswith("N") else None
            nominal_read = bool(nominal_surface) and not any(
                t.tag in {"XSV", "XSA"} or t.tag=="MM" and t.form=="한" for t in tokens[i+1:i+3])
            if nominal_read:
                kind = "read"
                nominal_head_starts.add(head_start)
            record_mode = ""
            record_candidates = [o for o in local_objects if o.kind == "record"
                                 and o.span[1] <= clause.span[0] + token.start]
            # A unique parser record NP and its locative/topic particles, never nearest NP.
            container = record_candidates[0] if len(record_candidates) == 1 else None
            location = [] if container is None else [t for t in tokens if
                container.span[1]-clause.span[0] <= t.start < token.start and t.tag in {"JKB","JX"}
                and not source[container.span[1]:clause.span[0]+t.start].strip()]
            located_record = container is not None and any(t.form in {"에","은","는"} for t in location)
            if token.tag.startswith("VV") and token.form in {"적히","쓰이"} and located_record:
                kind, record_mode = "record_assert", "passive_record_state"
            if token.form == "있" and token.tag.startswith(("VA","VV","VX")) and located_record:
                content_nouns = [t for t in tokens[max(0,i-3):i] if t.form == "내용" and t.tag.startswith("N")]
                if len(content_nouns) == 1 and any(t.tag == "JKS" and t.form in {"이","가"}
                    for t in tokens if content_nouns[0].start+content_nouns[0].len <= t.start < token.start):
                    kind, record_mode = "record_assert", "record_content_existence"
                    head_start = content_nouns[0].start
            if kind == "record_assert" and located_record and not record_mode:
                record_mode = "explicit_record_writing"
            if record_mode:
                record_modes[(i,head_start)] = (record_mode,container.object_id)
            if not kind:
                continue
            end_index = next((j for j in range(i,len(tokens)) if tokens[j].start+tokens[j].len>=token.start+len(nominal_surface.group())),i) if nominal_read else i if token.tag=="MM" and kind=="read" else next(
                (j for j in range(i+1,len(tokens)) if tokens[j].tag in {"ETM","ETN","EC","EF","SF"}),i)
            # An EC followed by VX (읽고 있던, 읽지 않았던) is inside
            # the same predicate. The final ending governs its relative noun.
            while tokens[end_index].tag == "EC" and end_index + 1 < len(tokens) and tokens[end_index+1].tag == "VX":
                auxiliary = end_index + 1
                end_index = next((j for j in range(auxiliary+1, len(tokens))
                                  if tokens[j].tag in {"ETM", "ETN", "EC", "EF", "SF"}), auxiliary)
            ending = tokens[end_index]
            head_end = max(token.start+token.len,ending.start+ending.len)
            heads.append((i,end_index,head_start,head_end,kind))
        terminal_read=re.search(r"(?:완독|재독|정주행)\s*[.!]?\s*$",text)
        if terminal_read and not any(h[4]=="read" for h in heads):
            terminal_index=next((i for i,t in enumerate(tokens) if t.start>=terminal_read.start()),None)
            if terminal_index is not None:
                last_index=max(i for i,t in enumerate(tokens) if not t.tag.startswith("S"))
                heads.append((terminal_index,last_index,terminal_read.start(),terminal_read.start()+len(terminal_read.group().strip(' .!')),"read"))
        for ordinal, (i,end_index,start,end,kind) in enumerate(heads):
            actor_evidence = ()
            actor_reason = "implicit_subject_default"
            nominal_read=start in nominal_head_starts
            preceding_head_end = heads[ordinal-1][3] if ordinal else 0
            next_head_start = heads[ordinal+1][2] if ordinal+1 < len(heads) else len(text)
            ending = tokens[end_index]
            preceding_subjects = [s for s in subjects if s[0] <= start]
            # All attributive predicates create an embedded argument scope,
            # including recommendation/gift verbs that are not reading heads.
            embedded_subjects=set()
            for j,t in enumerate(tokens[:i]):
                if t.tag=="ETM":
                    governing_verb=next((v for v in reversed(tokens[:j]) if v.tag.startswith("VV") or v.tag in {"VX","XSV","XSA"}),None)
                    if j and tokens[j-1].tag.startswith("VA"):
                        continue
                    if governing_verb and governing_verb.form not in {"지나"}:
                        governed=[s for s in preceding_subjects if s[0]<=governing_verb.start]
                        governing_quote=next(((a,b) for a,b in quote_spans if a<=governing_verb.start<b),None)
                        if governing_quote:
                            governed=[s for s in governed if governing_quote[0]<=s[0]<governing_quote[1]]
                        if governed:
                            subject_position=governed[-1][0]
                            subject_token=next(t for t in tokens if t.start==subject_position and t.form in human_forms)
                            subject_next=next((t for t in tokens if t.start>=subject_token.start+subject_token.len and t.tag in {"JKS","JX"}),None)
                            if len(governed)==1 and subject_next and subject_next.tag=="JX":
                                continue
                            embedded_subjects.add(governed[-1][0])
            preceding_subjects=[s for s in preceding_subjects if s[0] not in embedded_subjects]
            if kind in {"speech","hearsay"}:
                preceding_subjects=[s for s in subjects if s[0]<=start and not any(a<=s[0]<b for a,b in quote_spans)]
            if kind!="read" and len(preceding_subjects)>1:
                nested_subjects=set()
                for previous in heads[:ordinal]:
                    previous_ending=tokens[previous[1]]
                    if previous[4]=="read" and (previous_ending.tag=="ETM" or previous_ending.form in {"다고","다며"}):
                        readers=[s for s in preceding_subjects if s[0]<=previous[2]]
                        if len(readers)>1:
                            nested_subjects.add(readers[-1][0])
                preceding_subjects=[s for s in preceding_subjects if s[0] not in nested_subjects]
            actor = preceding_subjects[-1][1] if preceding_subjects else "author"
            if preceding_subjects:
                subject = next(t for t in tokens if t.start == preceding_subjects[-1][0])
                particle = next((t for t in tokens if t.start >= subject.start+subject.len and t.tag in {"JKS","JX"}), None)
                actor_evidence = ((clause.span[0]+subject.start,
                                   clause.span[0]+(particle.start+particle.len if particle else subject.start+subject.len)),)
                actor_reason = "governing_subject_after_embedded_subject_exclusion"
            outer_reports=[p for p in predicates if p.clause_id==clause.clause_id and p.predicate=="speech"
                           and p.actor=="other" and source[slice(*p.head_span)].endswith("길")]
            if outer_reports:
                actor="other"
                actor_evidence = (outer_reports[-1].head_span,)
                actor_reason = "outer_report_speaker_controls_content_actor"
            own_subject_start = preceding_subjects[-1][0] if preceding_subjects else 0
            grammatical_subject_value=actor if actor_evidence else "NOT_OBSERVED"
            grammatical_subject_evidence=actor_evidence
            following = tokens[end_index+1:]
            noun_head = next((t for t in following if t.tag.startswith("N") or t.tag == "MM"),None)
            copular_readers=[]
            reader_field=None
            # In a relative clause, the following person is the reader. A
            # later main-clause subject cannot reach backwards through it.
            if kind == "read" and ending.tag == "ETM" and noun_head and noun_head.form in human_forms:
                actor = "author" if noun_head.form in self_forms else "other"
                actor_evidence = ((clause.span[0]+noun_head.start, clause.span[0]+noun_head.start+noun_head.len),)
                actor_reason = "adnominal_predicate_reader_np"
            if kind == "read" and noun_head and noun_head.form in {"사람","독자","것","거","건"}:
                governing_check_start=next((h[2] for h in heads[ordinal+1:] if h[4]=="confirm"),len(text))
                copular_readers = [t for t in following if t.form in human_forms and t.start<governing_check_start]
                if copular_readers:
                    copular_reader=copular_readers[-1] if re.search(r"아니라",text[end:copular_readers[-1].start]) else copular_readers[0]
                    actor = "author" if copular_reader.form in self_forms else "other"
                    actor_evidence = ((clause.span[0]+copular_reader.start, clause.span[0]+copular_reader.start+copular_reader.len),)
                    actor_reason = "copular_reader_identity_np"
            if kind=="read" and nominal_read:
                reader_field=next((t for t in following if t.form in {"독서자","독자"}),None)
                if reader_field:
                    field_readers=[t for t in following if t.form in human_forms and t.start>reader_field.start]
                    if field_readers:
                        actor="author" if field_readers[0].form in self_forms else "other"
                        actor_evidence = ((clause.span[0]+field_readers[0].start, clause.span[0]+field_readers[0].start+field_readers[0].len),)
                        actor_reason = "nominal_reader_field_np"
            if kind=="assert" and ordinal+1<len(heads) and heads[ordinal+1][4]=="confirm" and ending.tag in {"EC","ETM","ETN"}:
                governing_subjects=[s for s in subjects if s[0]<=heads[ordinal+1][2]]
                if governing_subjects:
                    actor=governing_subjects[-1][1]
                    subject=next(t for t in tokens if t.start==governing_subjects[-1][0])
                    actor_evidence=((clause.span[0]+subject.start,clause.span[0]+subject.start+subject.len),)
                    actor_reason="governing_confirmation_subject"
            speaker = "commenter" if role == "comment" else "author"
            if role == "comment" and actor == "author":
                actor = "commenter"
            prefix = text[max(preceding_head_end,own_subject_start):start]
            suffix = text[end:min(len(text),next_head_start)]
            nominal_suffix = text[end:heads[ordinal+1][3]] if ordinal+1 < len(heads) and heads[ordinal+1][4] == "assert" else suffix
            scope_start = min(start, max(preceding_head_end,0))
            if kind=="confirm" and ordinal and heads[ordinal-1][4]=="assert":
                scope_start=0
            if kind=="assert" and ordinal and heads[ordinal-1][4]=="record_assert" and tokens[heads[ordinal-1][1]].tag=="ETM":
                scope_start=0
            scope_end = min(len(text),max(end,next_head_start))
            next_arguments = [m.span[0]-clause.span[0] for m in local_mentions
                              if clause.span[0]+end <= m.span[0] < clause.span[0]+next_head_start]
            if kind in {"correct", "maintain", "withdraw"} and next_arguments:
                scope_end = min(next_arguments)
            if kind=="confirm" and ordinal+1<len(heads) and heads[ordinal+1][4]=="assert":
                scope_end=heads[ordinal+2][2] if ordinal+2<len(heads) else len(text)
            fragment = text[scope_start:scope_end]
            tail_tokens = tokens[i+1:end_index+1]
            modality = "direct"
            if (any(t.form == "겠" for t in tail_tokens)
                    or ending.tag == "ETM" and ending.form in {"ᆯ","을","ㄹ"}
                    or kind == "read" and re.search(r"내일|다음\s*(?:주|달|휴가|가을)|예정|계획",prefix)
                       and not any(t.form in {"었","았"} for t in tail_tokens)):
                modality = "future"
            if ending.tag == "EF" and (re.search(r"[?？]",text[end:]) or ending.form in {"나","냐","니","던가","을까","ᆯ까"}):
                modality = "question"
            if kind=="read" and any(ch in text for ch in '?？') and not any(a<=start<b for a,b in quote_spans):
                modality="question"
            if kind=="read" and ending.form in {"면","으면","다면","는다면","거든"}:
                modality="conditional"
            if kind=="identify" and ending.tag in {"ETN","EC","ETM"}:
                modality="reported"
            if kind in {"assert","publication_assert"} and (ending.form in {"다고","다는","다던","다며","다니"}
                    or ending.tag=="ETM" and noun_head and noun_head.form in {"말","소문","전언","얘기","듯","것"}):
                modality="reported"
            if kind=="assert" and (ending.form=="라고" or ending.form=="라" and ordinal+1<len(heads) and heads[ordinal+1][4] in {"hearsay","speech"}):
                modality="reported"
            if kind=="read" and ending.tag=="ETM" and re.match(r"\s*책(?:이)?라고",text[end:]):
                modality="reported"
            if ending.form in {"는지","은지","ᆫ지","을지","ᆯ지"}:
                modality="question"
            if kind!="read" and (ending.tag=="ETM" and ending.form in {"ᆯ","을","ㄹ"}
                    or re.search(r"걸|더라|더라고|대요|다더",ending.form)
                    or re.match(r"\s*(?:듯|수도|지도|봄|봐)",suffix)):
                modality="reported"
            if kind=="assert" and ending.form=="나" and re.match(r"\s*(?:보|봄)",suffix):
                modality="reported"
            if kind=="assert" and any(t.tag=="EC" and t.form=="나" for t in tail_tokens) and any(t.tag=="VX" and t.form=="보" for t in tail_tokens):
                modality="reported"
            if kind=="assert" and ending.tag=="ETN" and ordinal+1<len(heads) and heads[ordinal+1][4] in {"speech","hearsay"}:
                modality="reported"
            quoted = any(a <= start < b for a,b in quote_spans)
            if kind!="read" and quoted:
                modality="reported"
            if kind!="read" and ending.tag=="ETM" and noun_head and noun_head.form in record_forms:
                modality="reported"
            if ending.tag=="EF" and re.search(r"까|나요|습니까",ending.form):
                modality="question"
            if kind!="read" and re.search(r"(?:친구|동료|형|동생)(?:에게서|한테|의?\s*말로(?:는)?)",text[:start]):
                modality="reported"
            record_owner = "unknown"
            owner_evidence = ()
            record_container = None
            if kind == "read":
                record_tokens = [t for t in following if t.form in record_forms and t.start < next_head_start]
                # Reported-content endings and the lexical record container
                # create a content proposition, never an actual reading.
                reported_ending = ending.form in {"다고","다는","다던","다며","다니"}
                preceding_records = [o for o in local_objects if o.kind == "record" and o.span[0] <= clause.span[0]+start]
                # A bare clause-final completion noun is a nominal predicate
                # ("작품 완독"). Embedded record contents retain reported mood.
                nominal_predicate = (nominal_read and not preceding_records
                                     and not record_tokens and not reader_field
                                     and re.fullmatch(r"\s*[.!]?\s*", text[end:]) is not None)
                if nominal_read and not nominal_predicate or reported_ending or quoted or (preceding_records and re.search(r"적혀|쓰여|기록|메모|노트",text[:start]) and re.search(r"적|쓰|써|기록",suffix)):
                    if modality=="direct":
                        modality = "reported"
                    record_container = record_tokens[0] if record_tokens else None
                    owner_text = text[max(0,(record_container.start if record_container else start)-15):
                                      (record_container.start if record_container else start)]
                    owner = re.search(r"(?P<owner>내|제|나의|저의|친구의|동료의|형의)\s*$",owner_text)
                    if owner:
                        record_owner = "author" if owner.group("owner") in {"내","제","나의","저의"} else "other"
                        owner_base=max(0,(record_container.start if record_container else start)-15)
                        owner_evidence=((clause.span[0]+owner_base+owner.start("owner"),
                                         clause.span[0]+owner_base+owner.end("owner")),)
                        if record_owner == "other" and not preceding_subjects:
                            actor = "other"
                            actor_evidence=()
                            actor_reason="legacy_owner_based_actor_without_independent_reader_np"
                    elif preceding_records:
                        record_owner = preceding_records[-1].owner
                        if record_owner == "other" and not preceding_subjects:
                            actor = "other"
                            actor_evidence=()
                            actor_reason="legacy_record_owner_actor_without_independent_reader_np"
            stance = "asserted"
            if modality != "direct" or actor in {"other","commenter"} and kind == "read":
                stance = "reported"
            read_negative = kind == "read" and bool(re.search(r"(?:안|못)\s*$",prefix) or re.match(r"\s*지\s*(?:않|못)",suffix)
                                     or ending.form=="지" and re.match(r"\s*(?:는\s*)?(?:않|못)",suffix)
                                     or re.match(r"\s*(?:은\s*)?적(?:이|은)?\s*없",suffix)
                                     or re.match(r"\s*(?:것|거|건)(?:은|이|는)?\s*아니",nominal_suffix)
                                      or any(t.form in {"않", "못"} for t in tail_tokens))
            if read_negative:
                stance = "denied" if actor == "author" and modality == "direct" else "reported"
            if kind=="read" and (ending.form in {"는지", "은지", "ᆫ지", "을지", "ᆯ지"}
                                  or re.search(r"(?:적|것).{0,12}(?:인지|여부|모르)",suffix)):
                modality="question"
                stance="reported"
            nominal_reader=kind=="read" and bool(noun_head and noun_head.form in {"사람","독자"} or copular_readers)
            if nominal_reader:
                modality="reported"
                stance="reported"
                if re.search(r"아니|부정",suffix) and actor=="author":
                    actor="unknown"
                    actor_evidence=()
                    actor_reason="negated_nominal_reader_identity_not_asserted"
            if kind=="read" and modality=="reported" and not preceding_subjects and not nominal_reader:
                actor=actor if nominal_read and reader_field else record_owner if nominal_read and record_owner in {"author","other"} else "unknown"
                if actor == "unknown" or nominal_read and not reader_field:
                    actor_evidence=()
                    actor_reason="reported_content_reader_not_independently_observed"
                coordinated_readers = [s for s in subjects if s[0] <= start]
                if (coordinated_readers and all(s[1] == "author" for s in coordinated_readers)
                        and ordinal and tokens[heads[ordinal-1][1]].form in {"고", "며"}):
                    actor = "author"
            absolute_start, absolute_end = clause.span[0]+start,clause.span[0]+end
            left = [m for m in local_mentions if m.marker_span[1] <= absolute_start]
            right = [m for m in local_mentions if absolute_end <= m.span[0]]
            selected: List[EditionWorkMention] = []
            # A copular subject identifies the thing governed by the earlier
            # relative read: "what I read was A", rather than the earlier B.
            relative_identity = (kind in {"read","confirm"} and ending.tag == "ETM" and right and
                (re.search(r"(?:것|책|작품|소설)[은는이가]\s*$",source[absolute_end:right[0].span[0]])
                 or not left and right[0].span[0] < clause.span[0]+next_head_start))
            unbound_identity=False
            if relative_identity and kind=="read":
                following_identity=source[right[0].marker_span[1]:clause.span[1]]
                governing_check=next((h for h in heads[ordinal+1:] if h[4]=="confirm"),None)
                governing_subjects=[s for s in subjects if s[0]<=(governing_check[2] if governing_check else next_head_start)]
                if len(governing_subjects)>1 and governing_subjects[-1][0]<=start:
                    governing_subjects=governing_subjects[:-1]
                unbound_identity=bool(re.match(r"인지",following_identity.strip()) or
                    governing_check and governing_subjects and governing_subjects[-1][1]=="other")
            if relative_identity and not unbound_identity:
                selected = [right[0]]
            elif left:
                selected = [left[-1]]
                for previous in reversed(left[:-1]):
                    between = source[previous.marker_span[1]:selected[0].span[0]].strip()
                    if re.fullmatch(r"(?:과|와|및|하고|랑|,|그리고)\s*",between):
                        selected.insert(0,previous)
                    else:
                        break
            anonymous = [o for o in local_objects if o.kind == "anonymous_work" and o.span[1] <= absolute_start]
            anonymous = [o for o in anonymous if not selected or o.span[0] > selected[-1].marker_span[1]]
            if anonymous:
                noun = source[slice(*anonymous[-1].span)]
                if re.search(r"다른|한\s*권|한\s*책",noun):
                    selected = []
                    object_ids = (anonymous[-1].object_id,)
                else:
                    object_ids = (anonymous[-1].object_id,) if not selected else ()
            else:
                object_ids = ()
            if kind == "read" and ending.tag == "ETM" and not relative_identity:
                relative_object = next((o for o in local_objects if o.kind == "anonymous_work"
                                        and absolute_end <= o.span[0] < clause.span[0]+next_head_start
                                        and not source[absolute_end:o.span[0]].strip()), None)
                if relative_object:
                    selected = []
                    object_ids = (relative_object.object_id,)
            # A reported reading can govern the NP of a following relative
            # speech: "읽었다고 한 이 책". The NP owns the embedded reading.
            if kind == "read" and not selected and not object_ids and reported_ending:
                relative_object = next((o for o in local_objects if o.kind == "anonymous_work"
                    and absolute_end <= o.span[0]
                    and re.fullmatch(r"\s*(?:한|했던|하는)\s*", source[absolute_end:o.span[0]])), None)
                if relative_object:
                    object_ids = (relative_object.object_id,)
            if unbound_identity:
                selected=[]
                relative_object=next((o for o in local_objects if o.kind=="anonymous_work" and
                                     o.span[0]<=absolute_end<o.span[1]),None)
                object_ids=(relative_object.object_id,) if relative_object else ()
                modality="reported"
                stance="reported"
            if kind in {"confirm","assert"}:
                reader_slots=[o for o in local_objects if o.kind=="human_reader" and o.span[1]<=absolute_start]
                if not reader_slots and not local_mentions and not re.search(r"책|판본|기록|메모|노트",fragment):
                    reader_slots=[o for o in objects if o.kind=="human_reader" and o.source_index==clause.source_index
                                  and o.span[1]<=clause.span[0]]
                if reader_slots:
                    selected=[]
                    object_ids=(reader_slots[-1].object_id,)
            if not selected and not object_ids and not unbound_identity:
                prior = [m for m in mentions if m.source_index == clause.source_index and m.marker_span[1] <= clause.span[0]]
                if prior:
                    recent = [m for m in prior if m.paragraph_id == prior[-1].paragraph_id]
                    if len({m.work_id for m in recent}) == 1 and not re.search(r"다른\s*(?:책|작품)",fragment):
                        selected = [recent[-1]]
            if selected:
                object_ids = tuple(m.mention_id for m in selected)
            if kind=="read" and selected:
                object_suffix=source[max(clause.span[0],selected[-1].marker_span[1]):absolute_start]
                explicit_editions=re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)(?:을|를|만|은|이|가)(?=\s)",object_suffix)
                if explicit_editions and any(m.marker!=explicit_editions[-1].casefold() for m in selected):
                    object_ids=()
            if role == "comment" and kind == "read":
                # The person referred to by a comment and the comment's
                # speaker are separate roles, including another post's author.
                reader_np = re.search(r"(?:작성자|글쓴이)(?:가|는|이|은)\s*", text[:start])
                if reader_np:
                    document_prefix = text[:reader_np.start()]
                    other_document = re.search(r"(?:다른|친구(?:의)?|동료(?:의)?)\s*(?:게시물|게시글|글|원글)", document_prefix)
                    current_document = re.search(r"원글|(?:이|그|해당)\s*(?:게시물|게시글|글)", document_prefix)
                    actor = "other" if other_document else "author" if current_document else "unknown"
                    actor_evidence=((clause.span[0]+reader_np.start(),clause.span[0]+reader_np.end()),)
                    actor_reason="comment_document_author_reader_separate_from_speaker"
                    modality, stance = "reported", "reported"
            record_mode, record_id = record_modes.get((i,start),("",""))
            if record_mode in {"passive_record_state","record_content_existence"}:
                actor, actor_evidence, actor_reason = "unknown", (), "record_state_has_no_explicit_writer"
                grammatical_subject_value, grammatical_subject_evidence = "NOT_OBSERVED", ()
                modality, stance = "reported", "reported"
            full_span = _edition_native_span(native_sources, clause.source_index, (absolute_start, absolute_end))
            lexical = tokens[i]
            lexical_start = lexical.start if record_mode == "record_content_existence" else start
            lexical_end = lexical.start + lexical.len
            if start < lexical.start:
                compound = re.match(r"(?:완독|재독|정주행)",text[start:])
                if compound:
                    lexical_end=start+len(compound.group())
            if lexical_end <= lexical_start:
                lexical_end = end
            lexical_span = _edition_native_span(native_sources, clause.source_index,
                (clause.span[0]+lexical_start, clause.span[0]+min(lexical_end,end)))
            scope = _edition_native_span(native_sources, clause.source_index,
                (clause.span[0]+scope_start,clause.span[0]+scope_end))
            actor_proofs = tuple(_edition_native_span(native_sources, clause.source_index, s) for s in actor_evidence)
            temporal_tokens = [t for t in tail_tokens if t.tag == "EP" and t.form in {"었","았","였","겠"}]
            if kind=="read" and ending.tag=="ETM" and ending.form in {"은","ᆫ","ㄴ"}:
                temporal_tokens=tuple(temporal_tokens)+(ending,)
            tense = "future" if modality=="future" else "past" if any(t.form in {"었","았","였","은","ᆫ","ㄴ"} for t in temporal_tokens) else "NOT_OBSERVED"
            temporal_proofs = tuple(_edition_native_span(native_sources, clause.source_index,
                (clause.span[0]+t.start,clause.span[0]+t.start+t.len)) for t in temporal_tokens)
            # The old reported stance also withholds publication for other
            # readers and copular reader identities. It is not attribution.
            attribution = "quoted" if quoted else "reported" if modality=="reported" and not nominal_reader else "direct"
            mood = modality if modality in {"question","conditional","future","reported"} else (
                "completed" if kind=="read" and tense=="past" else "current")
            if kind=="read" and nominal_reader and tense=="past" and attribution=="direct":
                mood="completed"
            if kind=="read" and re.search(r"(?:어도|아도|더라도)\s*(?:된|되|괜찮|좋)",text[start:scope_end]):
                mood="permission"
            elif ending.tag=="EF" and re.search(r"(?:어라|아라|세요|십시오|줘)$",ending.form):
                mood="request"
            polarity="negative" if read_negative or stance=="denied" else (
                "positive" if kind=="read" or stance=="asserted" else "NOT_OBSERVED")
            target_objects=[o for o in local_objects if o.object_id in object_ids]
            target_kind="work" if selected else target_objects[-1].kind if target_objects else "NOT_OBSERVED"
            target_proofs=tuple(_edition_native_span(native_sources,clause.source_index,m.span) for m in selected)
            target_proofs += tuple(o.native_span for o in target_objects)
            # An accusative metadata/record NP can be read without reading the
            # named work. Preserve that grammatical object independently.
            accusative=[j for j,t in enumerate(tokens[:i]) if t.tag=="JKO"]
            if kind=="read" and accusative:
                nouns=[t for t in tokens[:accusative[-1]] if t.tag.startswith("N")]
                if nouns:
                    governed_noun=nouns[-1]
                    if governed_noun.form in record_forms:
                        target_kind="record_text"
                    elif governed_noun.form in {"제목","작품명","URL","주소","링크","목록","이름","표지","사진","화면","댓글","게시물"}:
                        target_kind="metadata_text"
                    if target_kind in {"record_text","metadata_text"}:
                        target_proofs=(_edition_native_span(native_sources,clause.source_index,
                            (clause.span[0]+governed_noun.start,clause.span[0]+governed_noun.start+governed_noun.len)),)
            fictional=bool(re.search(r"소설\s*(?:안|속)|작중|등장인물|주인공",text[:start]))
            actual_read = (kind=="read" and bool(actor_evidence) and polarity=="positive"
                           and attribution=="direct" and mood not in {
                               "permission","request","future","conditional","question","reported"}
                           and (tense=="past" or nominal_read)
                           and target_kind in {"work","anonymous_work"} and not fictional)
            trace = (
                EditionNativeDecision("grammatical_subject",grammatical_subject_value,
                    tuple(_edition_native_span(native_sources,clause.source_index,s) for s in grammatical_subject_evidence),
                    "governing_subject_before_reader_identity_override"),
                EditionNativeDecision("actor",actor,actor_proofs,actor_reason),
                EditionNativeDecision("reader",actor if kind=="read" and actor_evidence else "NOT_OBSERVED",
                    actor_proofs if kind=="read" else (),actor_reason if kind=="read" else "predicate_is_not_reading"),
                EditionNativeDecision("speaker",speaker,reason="source_role_attribution_without_explicit_speaker_np"),
                EditionNativeDecision("content_speaker","NOT_OBSERVED",reason="source_speaker_is_not_a_content_speaker_np"),
                EditionNativeDecision("record_owner",record_owner if owner_evidence else "NOT_OBSERVED",
                    tuple(_edition_native_span(native_sources,clause.source_index,s) for s in owner_evidence),
                    "explicit_possessive_owner" if owner_evidence else "owner_np_not_independently_observed"),
                EditionNativeDecision("modality",modality,(full_span,scope),"predicate_ending_quote_and_governed_scope"),
                EditionNativeDecision("mood",mood,(full_span,scope),"ending_and_reading_tense_or_permission_form"),
                EditionNativeDecision("attribution",attribution,(scope,),"quote_membership_and_reported_ending"),
                EditionNativeDecision("stance",stance,(full_span,scope),"predicate_negation_and_modality_scope"),
                EditionNativeDecision("polarity",polarity,(full_span,scope),"independent_read_negation_or_unasserted_content"),
                EditionNativeDecision("tense",tense,temporal_proofs,"morphological_tense_tokens" if temporal_proofs else "no_independent_tense_marker"),
                EditionNativeDecision("reading_target_kind",target_kind,target_proofs,"governed_source_object_and_accusative_nominal_head",object_ids),
                EditionNativeDecision("fictional_scope","fictional" if fictional else "NOT_OBSERVED",
                    (scope,) if fictional else (),"explicit_source_fictional_context_guard"),
                EditionNativeDecision("actual_read", "asserted" if actual_read else "NOT_OBSERVED",
                    (full_span,)+actor_proofs,"reading_tense_reader_attribution_polarity_conjunction_without_publication_authority"),
            )
            if record_mode:
                object_ids = tuple(dict.fromkeys(object_ids + (record_id,)))
                trace += (EditionNativeDecision("record_statement_form",record_mode,(full_span,),
                    "actual_token_form_tag_and_locative_record_np",(record_id,)),)
                if record_role_evidence is not None:
                    pid = f"{clause.clause_id}:predicate:{ordinal}"
                    rec = next(o for o in local_objects if o.object_id == record_id)
                    def parser_np(noun, particle, governance):
                        full = _edition_native_span(native_sources,clause.source_index,
                            (clause.span[0]+noun.start,clause.span[0]+particle.start+particle.len))
                        head = _edition_native_span(native_sources,clause.source_index,
                            (clause.span[0]+noun.start,clause.span[0]+noun.start+noun.len))
                        status = "OBSERVED" if full.status == head.status == "OBSERVED" else "NOT_OBSERVED"
                        return EditionNativeNP(full,head,(governance,),status,"actual_token_np_and_particle_boundaries")
                    owner_pairs = [(t,tokens[j+1]) for j,t in enumerate(tokens[:-1])
                        if rec.span[0] <= clause.span[0]+t.start < rec.span[1] and t.form in human_forms
                        and tokens[j+1].tag == "JKG" and tokens[j+1].form == "의"]
                    # Possessive pronouns with no overt 의 are only observed when the tokenizer supplies MM/NP.
                    owner_pronouns = [t for t in tokens if rec.span[0] <= clause.span[0]+t.start < rec.span[1]
                        and t.form in {"내","제"} and t.tag in {"MM","NP"}]
                    owner_np = parser_np(*owner_pairs[0],pid) if len(owner_pairs) == 1 else None
                    if owner_np is None and len(owner_pronouns) == 1:
                        t=owner_pronouns[0]; owner_np=parser_np(t,t,pid)
                    embedded = [h for h in heads[:ordinal] if h[4] == "read" and
                        tokens[h[1]].form in {"다고","라고","다는","다던","다며"}]
                    # Bare completion nouns followed by 라고 also retain actual token evidence.
                    embedded += [h for h in heads[:ordinal] if h[4] == "read" and h[2] in nominal_head_starts
                        and any(t.tag in {"EC","JKQ"} and t.form == "라고" for t in tokens[h[1]+1:i])]
                    embedded = list(dict.fromkeys(embedded))
                    content_np, content_span, read_pid = None, None, None
                    if len(embedded) == 1:
                        h=embedded[0]; read_pid=f"{clause.clause_id}:predicate:{heads.index(h)}"
                        people=[(t,tokens[j+1]) for j,t in enumerate(tokens[:-1]) if
                            rec.span[1] <= clause.span[0]+t.start < clause.span[0]+h[2]
                            and t.form in human_forms and tokens[j+1].tag == "JKS"]
                        if len(people) == 1: content_np=parser_np(*people[0],read_pid)
                        work_spans=[m.span for m in local_mentions if rec.span[1] <= m.span[0]
                                    and m.marker_span[1] <= clause.span[0]+h[2]]
                        content_start=(content_np.full_np.used_span[0] if content_np is not None and content_np.status == "OBSERVED"
                            else work_spans[0][0] if len(work_spans)==1 else None)
                        if content_start is not None:
                            content_span=_edition_native_span(native_sources,clause.source_index,(content_start,clause.span[0]+h[3]))
                    writer_np=None
                    if record_mode == "explicit_record_writing" and len(actor_evidence)==1:
                        pairs=[(t,tokens[j+1]) for j,t in enumerate(tokens[:-1]) if
                            clause.span[0]+t.start == actor_evidence[0][0] and t.form in human_forms
                            and tokens[j+1].tag in {"JKS","JX"}]
                        if len(pairs)==1: writer_np=parser_np(*pairs[0],pid)
                    record_role_evidence.append({'record_id':record_id,'predicate_id':pid,'statement_mode':record_mode,
                        'statement':_edition_native_span(native_sources,clause.source_index,(rec.span[0],absolute_end)),
                        'owner_np':owner_np,'content_span':content_span,'content_np':content_np,'content_predicate_id':read_pid,
                        'writer_np':writer_np,'token_witness':{'form':lexical.form,'tag':lexical.tag,'start':lexical.start,
                            'length':lexical.len,'ending_form':ending.form,'ending_tag':ending.tag},
                        'source_authority':'NOT_OBSERVED_SEMANTIC_ADOPTION_PENDING'})
            predicates.append(EditionSourcePredicate(
                f"{clause.clause_id}:predicate:{ordinal}",clause.clause_id,clause.source_id,clause.source_index,
                (absolute_start,absolute_end),(clause.span[0]+scope_start,clause.span[0]+scope_end),
                kind,actor,speaker,modality,stance,object_ids,record_owner,
                full_span,lexical_span,scope,trace))
    # A reading claim about a person and a quoted reading acquire current
    # authority only through an explicit author's own assertion/confirmation.
    for index,read in enumerate(predicates):
        if read.predicate!="read" or read.modality!="reported" or read.actor!="author":
            continue
        role,source=sources[read.source_index]
        if role!="post_body":
            continue
        clause=next(c for c in clauses if c.clause_id==read.clause_id)
        nominal=[o for o in objects if o.kind=="human_reader" and o.source_index==read.source_index
                 and read.head_span[0]<=o.span[0]<clause.span[1] and o.span[1]>=read.head_span[1]]
        checks=[p for p in predicates if p.source_index==read.source_index and p.head_span[0]>=read.head_span[1]
                and p.predicate in {"confirm","speech","assert"} and p.actor=="author" and p.modality=="direct"
                and (p.predicate!="assert" or source[slice(*p.head_span)].startswith("사실"))
                and (p.clause_id==read.clause_id or nominal and any(o.object_id in p.object_ids for o in nominal))]
        own_subject=bool(re.search(r"(?:나는|내가|저는|제가)(?:\s|,)",source[clause.span[0]:read.head_span[0]]))
        if nominal and not checks and not any(p.source_index==read.source_index and p.predicate in {"confirm","speech","hearsay"}
                and p.head_span[0]>read.head_span[1] for p in predicates):
            identity=source[read.head_span[1]:clause.span[1]]
            if re.search(r"(?:나|저)(?:다|였다|이다|이었다|이며|이고)",identity) and not re.search(r"아니|전언|소문|얘기",identity):
                predicates[index]=replace(read,modality="direct",stance="asserted",native_trace=read.native_trace+(
                    EditionNativeDecision("modality","direct",(_edition_native_span(native_sources,read.source_index,(read.head_span[1],clause.span[1])),),
                                          "explicit_nominal_reader_identity",previous_value=read.modality),
                    EditionNativeDecision("stance","asserted",reason="explicit_nominal_reader_identity",previous_value=read.stance)))
                predicates[index]=replace(predicates[index],native_trace=predicates[index].native_trace+(
                    EditionNativeDecision("actual_read","asserted",(predicates[index].native_scope,),
                        "explicit_reader_identity_authority",previous_value="NOT_OBSERVED"),))
                continue
        if not nominal and not own_subject:
            continue
        for check in checks:
            proof=source[read.head_span[0]:check.scope_span[1]]
            if re.search(r"소문|전언|얘기|들은|들었|듣|취소|부정|아니|없|틀렸|모르|인지|여부",proof):
                continue
            factual_assertion = (check.predicate == "assert" and bool(set(check.object_ids).intersection(read.object_ids))
                                 and re.search(r"사실(?:이었다|이다|임)", source[slice(*check.head_span)])
                                 and re.match(r"\s*말[은이]", source[read.head_span[1]:check.head_span[0]]))
            if not nominal and check.predicate!="speech" and not factual_assertion:
                continue
            predicates[index]=replace(read,modality="direct",stance="asserted",native_trace=read.native_trace+(
                EditionNativeDecision("modality","direct",(check.native_scope,),"governing_author_confirmation",(check.predicate_id,),read.modality),
                EditionNativeDecision("stance","asserted",(check.native_scope,),"governing_author_confirmation",(check.predicate_id,),read.stance)))
            predicates[index]=replace(predicates[index],native_trace=predicates[index].native_trace+(
                EditionNativeDecision("actual_read","asserted",(check.native_scope,),
                    "governing_author_confirmation",(check.predicate_id,),"NOT_OBSERVED"),))
            break
    return tuple(predicates)


def _edition_bind_source_propositions(
    sources: Tuple[Tuple[str, str], ...], mentions: Tuple[EditionWorkMention, ...],
    candidates: Tuple[EditionSourceEvent, ...],
    adapters: Tuple[Tuple[str, EditionMarkerMention], ...],
    native_sources: Tuple[EditionNativeSource, ...] = (),
) -> EditionSourceLedger:
    """Bind source propositions, then freeze and reduce their event graph once.

    Legacy surface recognition supplies event proposals only. A reading proposal
    must agree with its source clause's object, actor and modality before it can
    participate in the current-edition reducer. Anonymous books and records have
    their own objects; a later identification can connect them to a work surface.
    """
    clauses = _edition_source_clauses(sources, native_sources)
    mention_by_id = {item.mention_id: item for item in mentions}
    adapter_by_id = dict(adapters)
    objects = [EditionSourceObject(
        item.mention_id, item.source_id, item.source_index, item.span, "work", item.mention_id,
        native_span=item.native_span,
        native_np=_edition_native_np(native_sources,item.source_index,item.span,marker_span=item.marker_span),
    ) for item in mentions]

    def clause_for(index: int, pos: int) -> Optional[EditionSourceClause]:
        return next((c for c in clauses if c.source_index == index and c.span[0] <= pos < c.span[1]), None)

    def source_actor(fragment: str, role: str) -> str:
        actor = _edition_proposition_actor(fragment)
        return ("commenter" if role == "comment" else "author") if actor == "implicit" else (
            "commenter" if role == "comment" and actor == "author" else actor)

    def positive_check(fragment: str) -> bool:
        try:
            token_list=list(_edition_kiwi().tokenize(fragment))
        except Exception:
            return False
        heads=[i for i,t in enumerate(token_list) if t.form in {"확인","검증","대조","비교","승인"}
               and any(v.tag=="XSV" for v in token_list[i+1:i+3]) or t.form=="맞추" and t.tag.startswith("VV")]
        outcome=bool(re.search(r"맞(?:다|습니다|았|아|다고|음)|사실(?:이다|이고|임|이라고)|정확|일치|(?:이었|였)(?:습니다|어요|다)",fragment))
        if re.search(r"인지|여부",fragment) and not outcome:
            return False
        if re.search(r"(?:안|못)\s*(?:확인|검증|대조|승인)|(?:확인|검증|대조|승인)하?\s*지\s*(?:는\s*)?(?:않|못)|예정|내일|취소|잘못|틀렸|아니|아마|추측|모르",fragment):
            return False
        if re.search(r"(?:확인|검증|대조|승인).{0,8}적.{0,4}없",fragment):
            return False
        if any(t.form=="겠" or t.tag=="EF" and t.form in {"ᆯ게","을게","ᆯ까","을까"} for t in token_list):
            return False
        return any(any(t.tag in {"EP","EF"} for t in token_list[i+1:]) or outcome for i in heads)

    def comment_identity_argument(target: EditionWorkMention, clause: EditionSourceClause) -> bool:
        """A check elsewhere in the comment cannot identify every named work.

        The named work must be the argument of an asserted check/match, or the
        immediate complement of a copula. A coordinated or relational noun
        between the work and the copula introduces a different proposition.
        """
        governed = [p for p in predicates if p.clause_id==clause.clause_id
                    and p.predicate in {"confirm","assert","speech"}
                    and p.modality=="direct" and p.stance=="asserted" and p.actor=="commenter"
                    and target.mention_id in p.object_ids]
        source=sources[target.source_index][1]
        def own_match(p: EditionSourcePredicate) -> bool:
            text=source[slice(*p.scope_span)]
            values=re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)(?:이라고|임|이었다|이다|[이가]\s*맞)",text)
            if values and values[-1].casefold()!=target.marker:
                return False
            if p.predicate=="speech":
                return any(inner.clause_id==p.clause_id and inner.predicate=="assert"
                    and inner.actor=="commenter" and target.mention_id in inner.object_ids
                    and re.search(r"맞|확실",source[slice(*inner.head_span)]) for inner in predicates)
            return positive_check(text) or p.predicate=="assert" and bool(re.search(r"맞|확실|단언|확신",source[slice(*p.head_span)]))
        if any(own_match(p) for p in governed):
            return True
        try:
            clause_tokens=list(_edition_kiwi().tokenize(source[slice(*clause.span)]))
            following=[t for t in clause_tokens if clause.span[0]+t.start>=target.marker_span[1]]
        except Exception:
            return False
        meaningful=[t for t in following if not t.tag.startswith("S")]
        # Kiwi can represent the same adjacent copular surface as pronoun
        # "이" plus VCP, especially immediately after a closing bracket.
        if len(meaningful)>1 and meaningful[0].tag=="NP" and meaningful[0].form=="이" and meaningful[1].tag=="VCP":
            meaningful=meaningful[1:]
        return bool(meaningful and meaningful[0].tag=="VCP"
                    and any(t.tag in {"EP","EF"} or t.tag=="EC" and t.form=="라고"
                            for t in meaningful[1:]))

    def current_document_argument(target: EditionWorkMention, clause: EditionSourceClause) -> bool:
        source=sources[clause.source_index][1]
        prefix=source[clause.span[0]:target.span[0]]
        references=list(re.finditer(r"원글|본문|(?:이|그|해당)\s*(?:글|게시글|게시물|포스트)",prefix))
        if not references:
            return False
        if re.search(r"(?:친구|동료|형|동생|다른|옆)(?:의)?(?:\s+\S+){0,2}\s*$",prefix[:references[-1].start()]):
            return False
        try:
            tail=list(_edition_kiwi().tokenize(prefix[references[-1].end():]))
        except Exception:
            return not re.search(r"(?:내|제|친구|동료)\s+.*(?:에는|은|는)",prefix[references[-1].end():])
        # A new subject/location NP after the document phrase owns the work
        # argument ("이 글은 ... 내 책장에는 A"). The document cannot reach it.
        return not any(t.tag in {"JKS","JX","JKB"} and t.start>3 for t in tail)

    for clause in clauses:
        role, text = sources[clause.source_index]
        chunk = text[slice(*clause.span)]
        for record in re.finditer(r"(?:내|제|나의|저의|친구(?:의)?|동료(?:의)?|형(?:의)?|동생(?:의)?)?\s*(?:(?:옛|독서|블로그|단행본|연재본)\s*)*(?:메모|기록|노트|수첩|독서장|독서표|독서일지|독후감|감상문|주장|후기|서평|글|문단|표기|판본|말(?=을|은|이))", chunk):
            ownership = record.group().strip()
            owner = ("other" if re.match(r"(?:친구|동료|형|동생)",ownership) else
                     "author" if re.match(r"(?:내|제|나의|저의)",ownership) else "unknown")
            if owner=="unknown" and role=="post_body" and _edition_document_target(chunk,role) in {"own_record","current_post"}:
                owner="author"
            objects.append(EditionSourceObject(
                f"{clause.clause_id}:record:{record.start()}", clause.source_id, clause.source_index,
                (clause.span[0]+record.start(), clause.span[0]+record.end()), "record",
                actor=owner if owner!="unknown" else clause.actor, predicate="record", modality="reported",owner=owner,
                native_span=_edition_native_span(native_sources,clause.source_index,
                    (clause.span[0]+record.start(),clause.span[0]+record.end())),
                native_np=_edition_native_np(native_sources,clause.source_index,
                    (clause.span[0]+record.start(),clause.span[0]+record.end())),
                native_trace=(EditionNativeDecision("owner",owner if owner!="unknown" else "NOT_OBSERVED",
                    (_edition_native_span(native_sources,clause.source_index,
                        (clause.span[0]+record.start(),clause.span[0]+record.end())),) if owner!="unknown" else (),
                    "record_possessive_or_current_document_target" if owner!="unknown" else "owner_not_observed"),
                    EditionNativeDecision("writer","NOT_OBSERVED",reason="record_owner_does_not_identify_writer"),
                    EditionNativeDecision("reader","NOT_OBSERVED",reason="record_owner_does_not_identify_content_reader")),
            ))
        for book in re.finditer(r"(?:이름을\s*잊은\s*)?다른\s*(?:책|작품)(?:\s*한\s*권)?|(?:그|이|같은)\s*(?:책|판본|단행본|연재본)|책\s*한\s*권|한\s*책|(?<!\S)책(?=[을은이가의]\s)", chunk):
            following = chunk[book.end():]
            read = bool(re.search(r"(?:읽|완독)(?:었|았|했|다)", following)
                        or book.group().startswith("읽은"))
            denied = bool(re.search(r"(?:안|못)\s*읽|읽\s*지\s*(?:않|못)|읽은\s*적이\s*없", following))
            objects.append(EditionSourceObject(
                f"{clause.clause_id}:book:{book.start()}", clause.source_id, clause.source_index,
                (clause.span[0]+book.start(), clause.span[0]+book.end()), "anonymous_work",
                actor=clause.actor, predicate="read" if read else "",
                modality="direct" if read and not denied and clause.modality=="direct" else "unknown",
                native_span=_edition_native_span(native_sources,clause.source_index,
                    (clause.span[0]+book.start(),clause.span[0]+book.end())),
                native_np=_edition_native_np(native_sources,clause.source_index,
                    (clause.span[0]+book.start(),clause.span[0]+book.end())),
            ))
        for reader in re.finditer(r"(?<!\w)(?:독자|사람)[은는이가]?|(?:읽은|본|완독한|재독한|정주행한)\s*(?:건|것|게)",chunk):
            objects.append(EditionSourceObject(
                f"{clause.clause_id}:reader:{reader.start()}",clause.source_id,clause.source_index,
                (clause.span[0]+reader.start(),clause.span[0]+reader.end()),"human_reader",
                native_span=_edition_native_span(native_sources,clause.source_index,
                    (clause.span[0]+reader.start(),clause.span[0]+reader.end())),
                native_np=_edition_native_np(native_sources,clause.source_index,
                    (clause.span[0]+reader.start(),clause.span[0]+reader.end()))))

    # A record object owns a content proposition; it is not the person who
    # actually read the work. Keep its source owner and work argument separate.
    for index,obj in enumerate(objects):
        if obj.kind not in {"record","human_reader","anonymous_work"}:
            continue
        clause=clause_for(obj.source_index,obj.span[0])
        if clause is None:
            continue
        local=[m for m in mentions if m.source_index==obj.source_index
               and clause.span[0]<=m.marker_span[0]<clause.span[1]]
        if obj.kind == "anonymous_work":
            surface = sources[obj.source_index][1][slice(*obj.span)]
            if re.match(r"(?:그|이|같은)\s+", surface) or surface == "책":
                following = [m for m in local if obj.span[1] <= m.span[0]]
                explicit_alias = next((m for m in following
                    if re.fullmatch(r"(?:은|는|이|가)?\s*", sources[obj.source_index][1][obj.span[1]:m.span[0]])
                    and re.match(r"(?:을|를)?\s*(?:뜻(?:하|한|했|합)|가리(?:키|킨|켰))", sources[obj.source_index][1][m.marker_span[1]:clause.span[1]])), None)
                if explicit_alias:
                    objects[index] = replace(obj, parent_object_id=explicit_alias.mention_id)
                    continue
                preceding = [m for m in mentions if m.source_index==obj.source_index and m.marker_span[1]<=obj.span[0]]
                intervening = [o for o in objects if o.kind=="anonymous_work" and o.source_index==obj.source_index
                               and preceding and preceding[-1].marker_span[1]<o.span[0]<obj.span[0]
                               and re.search(r"다른|한\s*권|한\s*책",sources[o.source_index][1][slice(*o.span)])]
                if preceding and not intervening:
                    objects[index] = replace(obj, parent_object_id=preceding[-1].mention_id)
                elif not preceding and obj.actor=="author":
                    following = [m for m in local if obj.span[1]<=m.span[0]]
                    if following and re.match(r"(?:은|는|이|가)(?:의\s*판본)?\s*$", sources[obj.source_index][1][obj.span[1]:following[0].span[0]]) and re.match(
                            r"(?:이|은|는)?(?:다|었다|었|입니다|이다|라고)",sources[obj.source_index][1][following[0].marker_span[1]:clause.span[1]].strip()):
                        objects[index]=replace(obj,parent_object_id=following[0].mention_id)
            continue
        if local:
            preceding=[m for m in local if m.marker_span[1]<=obj.span[0]]
            target=preceding[-1] if preceding else local[0]
            objects[index]=replace(obj,parent_object_id=target.mention_id)
    record_role_evidence: List[Mapping[str,Any]] = []
    predicates = _edition_source_predicates(sources,mentions,clauses,tuple(objects),native_sources,record_role_evidence)
    # An author can explicitly name the same deictic book in a later source
    # assertion. This alias belongs to source discourse, never the catalog.
    for index,obj in enumerate(objects):
        if obj.kind!="anonymous_work" or obj.parent_object_id or not re.match(r"(?:이|그)\s+책",sources[obj.source_index][1][slice(*obj.span)]):
            continue
        following_aliases=[o for o in objects if o.kind=="anonymous_work" and o.source_index==obj.source_index
                           and o.span[0]>obj.span[1] and o.parent_object_id and o.actor=="author" and re.match(r"(?:이|그)\s+책",sources[o.source_index][1][slice(*o.span)])]
        if following_aliases and not re.search(r"다른\s*(?:책|작품)",sources[obj.source_index][1][obj.span[1]:following_aliases[0].span[0]]):
            objects[index]=replace(obj,parent_object_id=following_aliases[0].parent_object_id)
    # A deictic book keeps its own source object, with an explicit antecedent
    # edge to the work NP. Both IDs are recorded on the governing predicate.
    object_by_id = {o.object_id:o for o in objects}
    predicates = tuple(replace(p,object_ids=tuple(dict.fromkeys(p.object_ids + tuple(
        object_by_id[i].parent_object_id for i in p.object_ids
        if i in object_by_id and object_by_id[i].kind=="anonymous_work"
        and object_by_id[i].parent_object_id)))) for p in predicates)
    for index,obj in enumerate(objects):
        if obj.kind!="record" or obj.owner!="unknown":
            continue
        writers=[p for p in predicates if p.source_index==obj.source_index and p.predicate=="record_assert"
                 and p.actor=="other" and p.head_span[1]<=obj.span[0]<p.scope_span[1]
                 and re.search(r"쓴|적은",sources[obj.source_index][1][slice(*p.head_span)])
                  and not any(d.dimension=="record_statement_form" and d.value in {"passive_record_state","record_content_existence"} for d in p.native_trace)]
        if writers:
            objects[index]=replace(obj,owner="other",actor="other",native_trace=obj.native_trace+(
                EditionNativeDecision("owner","other",(writers[-1].native_full_predicate,),
                    "record_written_by_other",(writers[-1].predicate_id,),obj.owner),
                EditionNativeDecision("writer","other",tuple(p for d in writers[-1].native_trace
                    if d.dimension=="actor" for p in d.proofs),"explicit_governing_writer",(writers[-1].predicate_id,))))
    for index,obj in enumerate(objects):
        governed=tuple(p.predicate_id for p in predicates if obj.object_id in p.object_ids)
        writing=[p for p in predicates if obj.kind=="record" and p.predicate=="record_assert"
            and p.source_index==obj.source_index and p.scope_span[0]<=obj.span[0]<p.scope_span[1]
            and re.search(r"적|쓰|쓴|기록|기재",sources[p.source_index][1][slice(*p.head_span)])
            and not any(d.dimension=="record_statement_form" and d.value in {"passive_record_state","record_content_existence"} for d in p.native_trace)]
        writer_trace=(EditionNativeDecision("writer",writing[-1].actor,
            tuple(proof for d in writing[-1].native_trace if d.dimension=="actor" for proof in d.proofs),
            "governing_record_writing_predicate",(writing[-1].predicate_id,)),) if writing else ()
        objects[index]=replace(obj,native_np=replace(obj.native_np,governed_predicate_ids=governed),
                               native_trace=obj.native_trace+writer_trace)
    # A legacy label does not create a reading. Only a source verb with its
    # independently governed reader, modality and object can create the edge.
    source_record_mentions={i for p in predicates if p.predicate=="read" and p.modality=="reported"
                            for i in p.object_ids}
    validated_candidates = [e for e in candidates if e.predicate!="read" and not(
        e.predicate=="record" and e.object_mention_id in source_record_mentions) and not(
        e.predicate=="identify" and e.stance=="asserted" and e.object_mention_id in source_record_mentions)]
    for predicate in predicates:
        if predicate.predicate!="read":
            continue
        for object_id in predicate.object_ids:
            if object_id not in mention_by_id:
                for index,obj in enumerate(objects):
                    if obj.object_id==object_id:
                        objects[index]=replace(obj,actor=predicate.actor,predicate="read",modality=predicate.modality)
                continue
            container=next((o for o in objects if o.kind=="record" and o.parent_object_id==object_id
                            and predicate.scope_span[0]<=o.span[0]<predicate.scope_span[1]),None)
            is_record=predicate.modality=="reported"
            validated_candidates.append(EditionSourceEvent(
                f"{object_id}:source:{predicate.predicate_id}",object_id,predicate.head_span,
                "record" if is_record else "read",predicate.actor,predicate.speaker,predicate.modality,
                "unresolved" if is_record else predicate.stance,
                clause_id=predicate.clause_id,evidence_source_id=predicate.source_id,
                object_id=container.object_id if is_record and container else object_id,
                time="future" if predicate.modality=="future" else "current",
                predicate_head_span=predicate.head_span, source_proven=True))
    candidate_ids={e.event_id for e in validated_candidates}
    validated_candidates=[replace(e,supersedes_event_id=f"{e.object_mention_id}:claim")
        if e.supersedes_event_id and e.supersedes_event_id not in candidate_ids else e
        for e in validated_candidates]
    class NativeEventList(list):
        def append(self, event: EditionSourceEvent) -> None:
            index = next((i for i,s in enumerate(native_sources) if s.source_id==event.evidence_source_id),-1)
            matches=[p for p in predicates if p.source_id==event.evidence_source_id
                     and p.head_span==event.predicate_head_span]
            predicate=next((p for p in matches if p.predicate_id==event.predicate_id),
                           matches[0] if len(matches)==1 else None)
            native = _edition_native_span(native_sources,index,event.evidence_span)
            head = _edition_native_span(native_sources,index,event.predicate_head_span)
            trace = predicate.native_trace if predicate else ()
            trace += tuple(EditionNativeDecision(d,str(v),(native,),"native_event_creation_value") for d,v in (
                ("event_actor",event.actor),("event_speaker",event.speaker),
                ("event_modality",event.modality),("event_stance",event.stance),("event_time",event.time)))
            trace += (EditionNativeDecision("source_proven",str(event.source_proven),(native,),"source_binding_value_not_actual_read"),
                      EditionNativeDecision("supports_publish",str(event.supports_publish),(native,),"event_eligibility_not_final_publication"))
            super().append(replace(event,native_evidence=native,native_predicate=head,
                predicate_id=predicate.predicate_id if predicate else event.predicate_id,
                native_trace=trace+event.native_trace))
    bound: List[EditionSourceEvent] = NativeEventList()
    for proposed in validated_candidates:
        target = mention_by_id[proposed.object_mention_id]
        role, source = sources[target.source_index]
        clause = clause_for(target.source_index, target.marker_span[0])
        if clause is None:
            continue
        fragment = source[slice(*clause.span)]
        before = source[clause.span[0]:target.span[0]]
        after = source[target.marker_span[1]:clause.span[1]]
        predicate_clause = next((c for c in clauses if c.clause_id==proposed.clause_id),clause)
        event = replace(proposed, clause_id=predicate_clause.clause_id, evidence_source_id=target.source_id,
                        object_id=proposed.object_id or target.mention_id, speaker="commenter" if role=="comment" else proposed.speaker,
                        time=proposed.time if proposed.clause_id else "future" if clause.modality=="future" else "past" if re.search(r"어제|지난|작년", fragment) else "current")
        if not event.source_proven:
            event=replace(event,modality="unknown",stance="unresolved",
                          source_proven=event.predicate=="claim",
                          predicate_head_span=target.marker_span if event.predicate=="claim" else ())
        if event.source_proven and role == "comment" and proposed.stance == "asserted" and (event.predicate == "identify" or adapter_by_id.get(target.mention_id) and adapter_by_id[target.mention_id].basis == "bound_comment_identify"):
            event = replace(event, predicate="identify", stance="asserted")
            event = replace(event, actor="commenter", edge_kind="identifies_original_post")
        if event.supersedes_event_id:
            event = replace(event, edge_kind="corrects" if event.predicate=="record" else "confirms")
        bound.append(event)

    def add(target: EditionWorkMention, clause: EditionSourceClause, predicate: str, stance: str,
            actor: str, edge: str="", previous: Optional[str]=None, object_id: str="") -> None:
        governed=[p for p in predicates if p.clause_id==clause.clause_id and p.modality=="direct"
                  and (target.mention_id in p.object_ids or object_id and object_id in p.object_ids)]
        head=governed[-1].head_span if governed else target.marker_span
        bound.append(EditionSourceEvent(
            f"{target.mention_id}:proposition:{len(bound)}", target.mention_id, clause.span,
            predicate, actor, "commenter" if target.source_role=="comment" else "author",
            "direct", stance, previous, clause.clause_id, clause.source_id,
            object_id or target.mention_id, "current", edge,
            predicate_head_span=head,source_proven=True,
            predicate_id=governed[-1].predicate_id if governed else "",
        ))

    # Independent predicate scopes repair the legacy proposal's actor/object
    # combination, while the reducer below is the only authority for approval.
    for clause in clauses:
        role, source = sources[clause.source_index]
        fragment = source[slice(*clause.span)]
        local = [m for m in mentions if m.source_index==clause.source_index
                 and clause.span[0]<=m.marker_span[0]<clause.span[1]]
        prior = [m for m in mentions if m.source_index==clause.source_index and m.marker_span[1]<=clause.span[0]]
        if role == "post_body" and local:
            target = local[-1]
            prefix = source[clause.span[0]:target.span[0]]
            suffix = source[target.marker_span[1]:clause.span[1]].strip()
            if re.match(r"^(?:임을|이라는\s*최종\s*결론)",suffix) and positive_check(fragment):
                add(target,clause,"identify","asserted" if clause.actor=="author" else "reported",clause.actor)
        if role=="post_body" and not local and prior and clause.actor=="author" and positive_check(fragment):
            previous = prior[-1]
            earlier = sources[previous.source_index][1][:clause.span[0]]
            question = re.search(r"인지.{0,30}(?:물었|궁금)",earlier)
            if question and (re.search(r"그\s*판본.{0,12}맞다고",fragment) or re.fullmatch(r"(?:나는\s*)?(?:오늘|방금)?\s*직접\s*확인했다[.!]?",fragment.strip())):
                add(previous,clause,"identify","asserted","author")
        # Anonymous original-post objects can be identified by a commenter's
        # direct bibliographic check. The commenter never becomes the author.
        current_document = re.search(r"원글|본문|(?:이|그|해당)\s*(?:글|게시글|게시물|포스트)",source)
        if role == "comment" and local and current_document:
            text = source
            for target in local:
                denials=[p for p in predicates if p.clause_id==clause.clause_id and p.actor=="commenter"
                         and p.modality=="direct" and p.predicate=="assert" and target.mention_id in p.object_ids
                         and (re.search(r"아니|아님|틀렸|잘못",source[slice(*p.head_span)])
                              or re.search(r"확신",source[slice(*p.head_span)]) and re.search(
                                  r"(?:단행본|연재본)(?:이라고|임|이다)",source[slice(*p.scope_span)])
                              and not re.search(re.escape(target.marker)+r"(?:이라고|임|이다)",source[slice(*p.scope_span)]))]
                if denials and current_document_argument(target,clause):
                    add(target,clause,"identify","denied","commenter","identifies_original_post")
            explicit_match=any(p.source_index==clause.source_index and p.predicate=="assert" and p.modality=="direct"
                and p.stance=="asserted" and p.actor=="commenter" and re.search(r"맞|확실|단언|확신",source[slice(*p.head_span)]) for p in predicates)
            explicit_match=explicit_match or any(p.source_index==clause.source_index and p.predicate=="speech"
                and p.actor=="commenter" and p.modality=="direct" and any(inner.predicate=="assert"
                    and inner.clause_id==p.clause_id and inner.actor=="commenter" and re.search(r"맞|확실",source[slice(*inner.head_span)])
                    for inner in predicates) for p in predicates)
            if ((positive_check(text) or explicit_match) and not re.search(r"다른\s*글|친구의\s*(?:원글|글)|제가.{0,12}따로",text)
                    and not re.search(r"(?:아마|추측|것\s*같|모르|예정|수도)",text)):
                eligible = [o for o in objects if o.kind=="anonymous_work"
                            and sources[o.source_index][0]=="post_body"
                            and o.actor=="author" and o.modality=="direct"]
                explicit_other = bool(re.search(r"다른\s*(?:책|작품)",text))
                if explicit_other:
                    eligible = [o for o in eligible if re.search(r"다른\s*(?:책|작품)", sources[o.source_index][1][slice(*o.span)])]
                if not eligible:
                    for target in local:
                        post_mentions = [m for m in mentions if m.source_role in {"post_title","post_body"}]
                        base = _EDITION_MARKER_RE.sub("",target.title).strip()
                        anchors = [(index,t,re.search(r"(?<!\w)"+re.escape(base)+r"(?!\w)",t))
                                   for index,(r,t) in enumerate(sources) if r in {"post_title","post_body"}]
                        anchor = next(((i,t,m) for i,t,m in reversed(anchors) if m),None)
                        post_named = any(m.work_id==target.work_id for m in post_mentions) or not post_mentions and anchor is not None
                        if comment_identity_argument(target,clause) and post_named and current_document_argument(target,clause):
                            parent = next((e for e in reversed(bound) if e.object_mention_id in {
                                m.mention_id for m in post_mentions if m.work_id==target.work_id}),None)
                            if parent is None and anchor:
                                index,_,match=anchor
                                anchor_id=f"{target.mention_id}:original_work:{index}:{match.start()}"
                                objects.append(EditionSourceObject(anchor_id,f"{sources[index][0]}:{index}",index,
                                    match.span(),"original_post_work",parent_object_id=target.mention_id,
                                    native_span=_edition_native_span(native_sources,index,match.span()),
                                    native_np=_edition_native_np(native_sources,index,match.span())))
                                parent=EditionSourceEvent(anchor_id+":claim",target.mention_id,match.span(),
                                    "claim","unknown","author","unknown","unresolved",evidence_source_id=f"{sources[index][0]}:{index}",
                                    object_id=anchor_id,predicate_head_span=match.span(),source_proven=True)
                                bound.append(parent)
                            add(target,clause,"identify","asserted","commenter","identifies_original_post",
                                previous=parent.event_id if parent else None)
                if eligible:
                    for target in local:
                        if comment_identity_argument(target,clause):
                            consumed = eligible[-1]
                            reads = [p for p in predicates if p.predicate=="read" and consumed.object_id in p.object_ids
                                     and p.actor=="author" and p.modality=="direct" and p.stance=="asserted"]
                            if not reads:
                                continue
                            reading = reads[-1]
                            parent_id = f"{consumed.object_id}:identified_read:{target.mention_id}"
                            bound.append(EditionSourceEvent(parent_id,target.mention_id,consumed.span,
                                "record","author","author","direct","asserted",clause_id=reading.clause_id,
                                evidence_source_id=reading.source_id,object_id=consumed.object_id,
                                predicate_head_span=reading.head_span,source_proven=True))
                            add(target,clause,"identify","asserted","commenter","identifies_original_post",
                                previous=parent_id,object_id=consumed.object_id)
    # Confirmation and revision govern their own source arguments. A later
    # predicate cannot lend its object or edition value to the earlier one.
    for predicate in predicates:
        if predicate.predicate not in {"confirm","assert","correct","withdraw","maintain","record_assert","identify","publication_assert","speech"} or predicate.modality!="direct":
            continue
        role,source=sources[predicate.source_index]
        if role!="post_body" or predicate.actor!="author":
            continue
        clause=next(c for c in clauses if c.clause_id==predicate.clause_id)
        fragment=source[slice(*predicate.scope_span)]
        clause_text=source[slice(*clause.span)]
        targets=[mention_by_id[i] for i in predicate.object_ids if i in mention_by_id]
        if not targets:
            targets=[mention_by_id[o.parent_object_id] for o in objects
                     if o.object_id in predicate.object_ids and o.parent_object_id in mention_by_id]
        local_records=[o for o in objects if o.kind=="record" and o.source_index==predicate.source_index
                       and clause.span[0]<=o.span[0]<predicate.head_span[1]]
        if any(source[slice(*o.span)].endswith("서평") and o.owner!="author" for o in local_records):
            continue
        prior_records=[o for o in objects if o.kind=="record" and o.source_index==predicate.source_index
                       and o.span[1]<=clause.span[0] and o.parent_object_id]
        record_reference=bool(re.search(r"(?:그|이|앞|이전|예전|옛)\s*(?:독서\s*)?(?:기록|메모|노트|주장|후기|독서\s*사실)",clause_text))
        if any(o.owner=="other" for o in local_records) and predicate.predicate in {"correct","withdraw","assert","confirm"}:
            continue
        if record_reference and prior_records:
            # A record reference follows record discourse, not the most recent
            # unrelated work/read. In particular "the earlier claim only"
            # does not retract the new reading in the intervening sentence.
            reference=prior_records[-1]
            targets=[mention_by_id[reference.parent_object_id]]
        edition_slot=bool(re.search(r"표기|판본",clause_text) or re.search(
            r"(?:단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)(?:으)?로",fragment))
        paragraph_reference = re.search(r"(첫|둘째|셋째|넷째|\d+)\s*문단",fragment)
        if paragraph_reference:
            label = paragraph_reference.group(1)
            paragraph_number = {"첫":0,"둘째":1,"셋째":2,"넷째":3}.get(label, int(label)-1 if label.isdigit() else -1)
            referenced = [m for m in mentions if m.source_index==predicate.source_index
                          and m.paragraph_id==paragraph_number and m.marker_span[1]<=predicate.head_span[0]]
            if referenced:
                targets = referenced
        if not targets and edition_slot and re.search(r"(?:위|직전)\s*문단",clause_text):
            prior=[m for m in mentions if m.source_index==predicate.source_index and m.marker_span[1]<=clause.span[0]]
            latest_paragraph=max((m.paragraph_id for m in prior),default=-1)
            referenced=[m for m in prior if m.paragraph_id==latest_paragraph]
            if len({m.work_id for m in referenced})>1:
                for target in referenced:
                    bound.append(EditionSourceEvent(
                        f"{target.mention_id}:ambiguous_revision:{predicate.predicate_id}",target.mention_id,
                        predicate.scope_span,"record","unknown","author","unknown","unresolved",
                        clause_id=predicate.clause_id,evidence_source_id=predicate.source_id,
                        object_id=target.mention_id,edge_kind="unresolved_correction"))
        if not targets:
            continue
        if (predicate.predicate=="confirm" and not local_records and any(
                p.clause_id==predicate.clause_id and p.predicate=="read" and p.actor=="unknown"
                and p.modality=="reported" and p.head_span[0]<predicate.head_span[0] for p in predicates)):
            continue
        if (predicate.predicate=="confirm" and any(p.clause_id==predicate.clause_id and p.predicate=="read"
                and p.actor=="other" and p.head_span[0]<predicate.head_span[0] for p in predicates)
                and not any(e.actor=="author" and e.predicate=="read" and e.stance=="asserted"
                            and e.object_mention_id in {t.mention_id for t in targets} for e in bound)):
            continue
        is_record=bool(local_records or record_reference or re.search(r"기록|메모|노트|독서\s*사실",clause_text))
        negative=bool(re.search(r"틀렸|잘못|아니|착오|오류|실수",fragment))
        positive=bool(re.search(r"맞|사실|정확|일치",fragment)) and not negative
        stance=""
        edge=""
        if predicate.predicate in {"identify","publication_assert","speech"}:
            if re.search(r"모르|인지|소문|전언|예정|제목|URL",fragment):
                continue
            if predicate.predicate=="speech" and not re.search(r"(?:이|라고|이라|단행본|연재본)",fragment):
                continue
            if predicate.predicate=="speech" and any(p.predicate=="read" and p.actor=="other"
                    and p.clause_id==predicate.clause_id and p.head_span[0]<predicate.head_span[0] for p in predicates):
                continue
            stance="asserted"
            edge="identifies_current_book"
        elif predicate.predicate=="confirm" and (positive_check(fragment) or source[slice(*predicate.head_span)].startswith("확정")):
            argument = source[predicate.scope_span[0]:predicate.head_span[0]]
            metadata_np = re.search(r"(?:제목|작품명|URL|주소|링크)(?:을|를|은|는|이|가)(?=\s)", argument)
            if metadata_np and not re.search(r"판본|독서\s*사실|완독\s*(?:사실|기록)", argument):
                for target in targets:
                    bound.append(EditionSourceEvent(
                        f"{target.mention_id}:metadata:{predicate.predicate_id}",target.mention_id,
                        predicate.scope_span,"metadata_confirm","author","author","direct","asserted",
                        clause_id=predicate.clause_id,evidence_source_id=predicate.source_id,
                        object_id=target.mention_id,predicate_head_span=predicate.head_span,
                        source_proven=True,supports_publish=False))
                continue
            if re.search(r"표지|사진|제목",fragment) and not re.search(r"판본|그\s*책|이\s*책|읽은|기록|메모|노트",fragment):
                continue
            uncertain_argument=any(p.clause_id==predicate.clause_id and p.modality=="question"
                                   and p.head_span[0]<predicate.head_span[0] for p in predicates)
            if uncertain_argument and not re.search(r"맞|사실|정확|일치|확정",fragment):
                continue
            # The observed replacement is a value of this confirmation, not
            # the old bracket attached to the prior source object.
            replacement=re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)(?:(?:으)?로|임|이었|이었다|이다|입니다)",fragment)
            stance="denied" if replacement and any(t.marker!=replacement[-1].casefold() for t in targets) else "asserted"
            edge="confirms"
        elif predicate.predicate=="assert" and (is_record or edition_slot or re.search(r"실제|단행본|연재본",fragment)) and (positive or re.search(r"(?:단행본|연재본)(?:이었다|이다|입니다|이었)",fragment)):
            following_checks=[p for p in predicates if p.clause_id==predicate.clause_id and p.predicate=="confirm"
                              and p.head_span[0]>predicate.head_span[0] and set(p.object_ids).intersection(predicate.object_ids)]
            if following_checks:
                continue
            stance="asserted"
            edge="confirms"
        elif predicate.predicate=="assert" and (is_record or edition_slot or targets) and negative:
            stance="denied"
            edge="corrects" if edition_slot else "withdraws"
        elif predicate.predicate=="withdraw" and (is_record or edition_slot):
            stance="denied"
            edge="withdraws"
        elif predicate.predicate=="correct" and edition_slot:
            direction=re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)(?:으)?로",fragment)
            if direction:
                stance="asserted" if all(t.marker==direction[-1].casefold() for t in targets) else "denied"
            else:
                stance="denied"
            edge="corrects"
        elif predicate.predicate=="maintain" and edition_slot:
            stance="asserted"
            edge="confirms"
        elif predicate.predicate=="record_assert" and re.search(r"직접",fragment) and not re.search(r"옛|예전|지난|친구|동료|잘못|아니|틀렸",fragment):
            content=[e for e in bound if e.predicate=="record" and e.actor=="author" and e.modality=="reported"
                     and e.evidence_span[0]<=predicate.head_span[0]]
            if content:
                stance="asserted"
                edge="confirms"
        if not stance:
            continue
        bibliographic_subject=re.search(r"(?:제목|작품명|URL|주소|링크)(?:은|는|이|가)\s*$",source[clause.span[0]:min(t.span[0] for t in targets)])
        if stance=="asserted" and bibliographic_subject:
            continue
        if stance=="asserted" and predicate.predicate=="assert":
            edition_values=re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)(?:이었다|이다|입니다|이었|[이가]\s*맞)",fragment)
            if edition_values and any(t.marker!=edition_values[-1].casefold() for t in targets):
                stance="denied"
                edge="corrects"
        if stance=="asserted" and predicate.predicate in {"confirm","assert"}:
            matching_readers = [p for p in predicates if p.predicate=="read"
                and p.source_index==predicate.source_index and p.head_span[0]<predicate.head_span[0]
                and (set(p.object_ids).intersection(predicate.object_ids)
                     or any(o.object_id in predicate.object_ids and o.parent_object_id in p.object_ids for o in objects))]
            if matching_readers and matching_readers[-1].actor=="other" and (
                    matching_readers[-1].clause_id==predicate.clause_id or record_reference
                    or not any(o.owner=="author" for o in local_records)):
                continue
        if stance=="denied" and predicate.predicate=="assert" and edition_slot:
            slot_markers=re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)\s*(?:표기|판본)",fragment)
            if slot_markers:
                targets=[t for t in targets if t.marker==slot_markers[-1].casefold()]
        if stance=="asserted" and predicate.predicate=="assert" and edition_slot:
            asserted_markers=re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)[이가은는]?\s*맞",fragment)
            if asserted_markers:
                targets=[t for t in targets if t.marker==asserted_markers[-1].casefold()]
            # A positive replacement value need not mention the slot again:
            # "단행본 표기는 틀렸고 연재본이 맞다" still asserts 연재본.
            bare_values = re.findall(r"(단행본|연재본|개정판|합본|특별판|완전판|전자책|이북)(?:이|가|은|는)?\s*맞",fragment)
            if bare_values:
                targets=[t for t in targets if t.marker==bare_values[-1].casefold()]
        target_works={t.work_id for t in targets}
        affected=[m for m in mentions if m.source_index==predicate.source_index and m.work_id in target_works
                  and (m.marker_span[0]<=predicate.head_span[1] or m.mention_id in predicate.object_ids)]
        for target in affected:
            prior_events=[e for e in bound if e.object_mention_id==target.mention_id and e.source_proven
                          and (e.predicate_head_span or e.evidence_span)[0]<predicate.head_span[0]]
            parent=max(prior_events,key=lambda e:(e.predicate_head_span or e.evidence_span),default=None)
            if stance=="asserted" and predicate.predicate=="correct" and not any(
                    e.actor=="author" and e.predicate in {"read","record"} for e in prior_events):
                continue
            record=next((o for o in reversed(local_records+prior_records) if o.parent_object_id
                         and mention_by_id[o.parent_object_id].work_id==target.work_id),None)
            bound.append(EditionSourceEvent(
                f"{target.mention_id}:source:{predicate.predicate_id}:{edge}",target.mention_id,
                clause.span if stance=="denied" and edition_slot else (predicate.scope_span[0],predicate.head_span[1]),
                "record" if is_record or edition_slot else "identify","author","author","direct",stance,
                parent.event_id if parent else None,predicate.clause_id,predicate.source_id,
                record.object_id if record else target.mention_id,"current",edge,
                predicate.head_span,True,
                predicate_id=predicate.predicate_id,
                withdrawal_scope=("edition_slot" if edition_slot else "record_claim" if is_record else "NOT_OBSERVED")
                    if edge in {"withdraws","corrects"} else "NOT_OBSERVED",
                withdrawal_target_event_ids=(parent.event_id,) if parent and edge in {"withdraws","corrects"} else (),
                withdrawal_target_object_ids=(record.object_id if record else target.mention_id,)
                    if edge in {"withdraws","corrects"} else (),
                withdrawal_proof=predicate.native_scope if edge in {"withdraws","corrects"} else EditionNativeSpan(),
                native_trace=(EditionNativeDecision("withdrawal_reference", "record_antecedent" if record_reference else
                    "specified_paragraph" if paragraph_reference else "edition_slot" if edition_slot else "NOT_OBSERVED",
                    (predicate.native_scope,),"native_target_selection_before_reducer",
                    tuple(t.mention_id for t in targets)),)))

    # Freeze the graph, then one source-ordered reducer creates compatibility
    # projections. No surface fallback can authorize after this boundary.
    frozen = tuple(bound)
    projections = []
    reductions = []
    for target in mentions:
        old = adapter_by_id.get(target.mention_id) or EditionMarkerMention(
            target.title,target.marker,target.source_role,target.source_index,"reported",False)
        events = [e for e in frozen if e.object_mention_id==target.mention_id]
        if not events and target.mention_id not in adapter_by_id:
            continue
        decisive = [e for e in events if e.source_proven and e.supports_publish and e.modality=="direct" and e.stance in {"asserted","denied"}
                    and (e.actor=="author" or (e.actor=="commenter" and e.edge_kind=="identifies_original_post"))]
        decisive.sort(key=lambda e:(int(e.evidence_source_id.rsplit(":",1)[-1]) if e.evidence_source_id else target.source_index,e.predicate_head_span or e.evidence_span))
        winner = decisive[-1] if decisive else None
        if any("ambiguous_revision" in e.event_id for e in events):
            winner = None
        polarity = winner.stance if winner else "reported"
        basis = ("bound_comment_identify" if winner and winner.actor=="commenter" else
                 "author_read" if winner and winner.predicate=="read" else
                 "current_post_record" if winner and winner.predicate=="record" else
                 "author_identify" if winner else "")
        reductions.append({
            "object_mention_id":target.mention_id,
            "input_event_ids":tuple(e.event_id for e in events),
            "ordered_eligible_event_ids":tuple(e.event_id for e in decisive),
            "winner_event_id":winner.event_id if winner else "NOT_OBSERVED",
            "support_event_ids":tuple(e.event_id for e in decisive if e.stance=="asserted"),
            "denial_event_ids":tuple(e.event_id for e in decisive if e.stance=="denied"),
            "invalidated_event_ids":tuple(dict.fromkeys(e.supersedes_event_id for e in events
                if e.supersedes_event_id and e.edge_kind in {"withdraws","corrects"} and e.stance=="denied")),
            "current_edition_authority":polarity,"basis":basis,
            "actual_read_event_ids":tuple(e.event_id for e in events if e.source_proven and e.predicate=="read"
                and next((d.value for d in reversed(e.native_trace) if d.dimension=="actual_read"),
                         "NOT_OBSERVED")=="asserted"),
            "final_publication":"NOT_OBSERVED",
            "rule":"source_order_last_eligible_event_unless_ambiguous_revision",
        })
        projections.append((target.mention_id,replace(old,polarity=polarity,
            current_post_relation=winner is not None,claim_status=polarity,basis=basis,
            reader_actor=winner.actor if winner else old.reader_actor,
            evidence_span=winner.evidence_span if winner else old.evidence_span)))
    ledger = EditionSourceLedger(mentions,frozen,tuple(projections),clauses,tuple(objects),predicates,candidates,
                                 native_sources,tuple(reductions))
    # New source anchors are historical evidence only, never publication supporters.
    anchors=[]; evidence=[]
    for item in record_role_evidence:
        records=[o for o in ledger.objects if o.object_id==item['record_id']]
        heads=[p for p in ledger.predicates if p.predicate_id==item['predicate_id']]
        if len(records)!=1 or len(heads)!=1:
            evidence.append({**item,'status':'NOT_OBSERVED','reason':'unique_actual_record_anchor_absent'})
            continue
        rec,p=records[0],heads[0]
        content=item['content_span']
        works=[m for m in ledger.work_mentions if content is not None and content.status=='OBSERVED'
            and m.source_id==p.source_id and content.used_span[0]<=m.span[0]<m.marker_span[1]<=content.used_span[1]]
        work=works[0].mention_id if len(works)==1 else ""
        event=EditionSourceEvent(p.predicate_id+':record_anchor',work,p.head_span,'record',p.actor,p.speaker,
            'reported','unresolved',clause_id=p.clause_id,evidence_source_id=p.source_id,object_id=rec.object_id,
            predicate_head_span=p.head_span,source_proven=False,supports_publish=False,
            native_evidence=item['statement'],native_predicate=p.native_full_predicate,
            predicate_id=p.predicate_id,native_trace=p.native_trace)
        anchors.append(event)
        embedded_event=None
        reads=[r for r in ledger.predicates if r.predicate_id==item['content_predicate_id']]
        if len(reads)==1 and item['content_span'] is not None and item['content_span'].status=='OBSERVED':
            r=reads[0]
            embedded_event=EditionSourceEvent(event.event_id+':content',work,r.head_span,'record',r.actor,r.speaker,
                'reported','unresolved',clause_id=r.clause_id,evidence_source_id=r.source_id,object_id=rec.object_id,
                predicate_head_span=r.head_span,source_proven=False,supports_publish=False,
                native_evidence=item['content_span'],native_predicate=r.native_full_predicate,predicate_id=r.predicate_id,
                native_trace=r.native_trace)
            anchors.append(embedded_event)
        evidence.append({**item,'status':'OBSERVED','record_object':rec,'predicate':p,'event':event,
                         'content_predicate':reads[0] if len(reads)==1 else None,'content_event':embedded_event})
    ledger=replace(ledger,events=ledger.events+tuple(anchors),record_role_lexical_evidence=tuple(evidence))
    record_hashes = []
    for group in ("native_sources","work_mentions","events","clauses","objects","predicates","legacy_proposals","native_reductions"):
        for ordinal, record in enumerate(getattr(ledger,group)):
            payload=json.dumps(asdict(record) if is_dataclass(record) else record,
                               ensure_ascii=False,sort_keys=True,separators=(",",":"))
            record_hashes.append({"pointer":f"/{group}/{ordinal}",
                                  "sha256":hashlib.sha256(payload.encode("utf-8")).hexdigest()})
    for ordinal,(mention_id,projection) in enumerate(ledger.projections):
        payload=json.dumps((mention_id,asdict(projection)),ensure_ascii=False,sort_keys=True,separators=(",",":"))
        record_hashes.append({"pointer":f"/projections/{ordinal}",
                              "sha256":hashlib.sha256(payload.encode("utf-8")).hexdigest()})
    return replace(ledger,native_provenance={
        "producer_module":__name__,"module_file":__file__,
        "module_raw_sha256":_edition_native_module_sha(),
        "spec_origin":getattr(__spec__,"origin",None),"package":__package__,
        "call_path":"_edition_source_ledger -> _edition_build_source_ledger -> _edition_bind_source_propositions",
        "record_hash_serialization":"UTF8_JSON_ensure_ascii_false_sort_keys_compact",
        "record_hashes":tuple(record_hashes),
        "comparison_answer_inputs":"NOT_OBSERVED",
        "actual_read_semantics":"source_asserts_completed_reading; external_fact_verification_NOT_OBSERVED",
    })

def _edition_source_ledger(sources: Iterable[Tuple[str, Any]]) -> EditionSourceLedger:
    raw = tuple(
        (str(role or "unknown"), str(value or ""))
        for role, value in sources
    )
    native_sources = _edition_native_sources(raw)
    normalized = tuple((s.source_role,s.used_text) for s in native_sources)
    return _edition_build_source_ledger(normalized,native_sources)


def _edition_candidate_mentions_from_ledger(
    ledger: EditionSourceLedger, candidate_title: str,
) -> Tuple[EditionMarkerMention, ...]:
    base = _title_key(_EDITION_MARKER_RE.sub("", candidate_title).strip())
    markers = set(edition_markers_in_text(candidate_title))
    owned = {
        item.mention_id for item in ledger.work_mentions
        if item.work_id == base and item.marker in markers
    }
    selected: List[EditionMarkerMention] = []
    for mention_id, projection in ledger.projections:
        if mention_id not in owned:
            continue
        projected = replace(projection, candidate_title=candidate_title)
        if projected.current_post_relation and projected.polarity in {"asserted", "denied"}:
            attached = any(
                event.object_mention_id == mention_id
                and event.source_proven and event.supports_publish
                and event.stance == projected.polarity
                and (event.actor == "author" or (event.actor == "commenter" and event.edge_kind == "identifies_original_post"))
                and event.modality == "direct"
                for event in ledger.events
            )
            if not attached:
                projected = replace(
                    projected, polarity="reported", current_post_relation=False,
                    claim_status="reported", basis="",
                )
        selected.append(projected)
    return tuple(selected)


def edition_marker_mentions_for_candidate_in_sources(
    sources: Iterable[Tuple[str, Any]], candidate_title: str,
) -> Tuple[EditionMarkerMention, ...]:
    """Read one candidate from the source-wide work and event ledger."""
    return _edition_candidate_mentions_from_ledger(
        _edition_source_ledger(sources), candidate_title,
    )


def edition_markers_for_candidate_from_sources(
    sources: Iterable[Tuple[str, Any]], candidate_title: str,
) -> Tuple[str, ...]:
    """Project the same final relation used by the typed publication gate."""
    if not edition_markers_in_text(candidate_title):
        return ()
    relation = edition_current_relation_from_sources(sources, candidate_title)
    return relation.markers if relation.status == "affirmed" else ()


def edition_current_relation_from_sources(
    sources: Iterable[Tuple[str, Any]], candidate_title: str,
) -> EditionCurrentRelation:
    """Reduce one candidate from the common source ledger."""
    chunks = tuple(sources)
    return _edition_current_relation_from_ledger(
        _edition_source_ledger(chunks), chunks, candidate_title,
    )


def _edition_current_relation_from_ledger(
    ledger: EditionSourceLedger, chunks: Tuple[Tuple[str, Any], ...],
    candidate_title: str, *, record_role_session: Optional[RolePass] = None,
) -> EditionCurrentRelation:
    """Keep publication precedence downstream of work/event attachment."""
    if record_role_session is not None:
        observe_consumed(record_role_session, ledger)
    markers = edition_markers_in_text(candidate_title)
    if not markers:
        raise ValueError("edition current relation requires a marked candidate")
    mentions = _edition_candidate_mentions_from_ledger(ledger, candidate_title)
    post_surface = "\n".join(
        str(value or "") for role, value in chunks if role in {"post_title", "post_body"}
    )
    candidate_base = _EDITION_MARKER_RE.sub("", candidate_title).strip()
    post_names_candidate = bool(candidate_base and re.search(
        r"(?<!\w)" + re.escape(candidate_base) + r"(?!\w)", post_surface,
    ))
    if not post_names_candidate:
        candidate_work_id = _title_key(candidate_base)
        original_post_checks = {
            event.object_mention_id for event in ledger.events
            if event.speaker == "commenter" and event.predicate == "identify"
            and (event.actor == "author" or (event.actor == "commenter" and event.edge_kind == "identifies_original_post")) and event.modality == "direct"
            and event.stance == "asserted"
        }
        post_names_candidate = any(
            item.mention_id in original_post_checks
            and item.work_id == candidate_work_id and item.marker in markers
            for item in ledger.work_mentions
        )
    decisive = None
    status = "unresolved"
    author_denial = [item for item in mentions if item.marker in markers
                     and item.source_role != "comment" and item.polarity == "denied"
                     and item.current_post_relation]
    author_direct = [item for item in mentions if item.marker in markers
                     and item.source_role != "comment" and item.polarity == "asserted"
                     and item.current_post_relation]
    comment_denial = [item for item in mentions if item.marker in markers
                      and item.source_role == "comment" and item.polarity == "denied"
                      and item.current_post_relation]
    comment_direct = [item for item in mentions if item.marker in markers
                      and item.source_role == "comment" and item.polarity == "asserted"
                      and item.current_post_relation and post_names_candidate]
    # A separate commenter cannot retract the post author's direct claim.
    # Among comments alone, an explicit original-post denial vetoes assent.
    last_denial_by_marker = {
        marker: max(i for i, item in enumerate(mentions)
                    if item in author_denial and item.marker == marker)
        for marker in {item.marker for item in author_denial}
    }
    surviving_direct = [
        item for i, item in enumerate(mentions)
        if item in author_direct and (
            item.marker not in last_denial_by_marker
            or (i > last_denial_by_marker[item.marker] and item.basis == "author_read")
        )
    ]
    if author_denial and not set(markers).issubset({item.marker for item in surviving_direct}):
        decisive, status = author_denial[-1], "denied"
    elif author_denial:
        decisive, status = surviving_direct[-1], "affirmed"
    elif set(markers).issubset({item.marker for item in author_direct}):
        decisive, status = author_direct[-1], "affirmed"
    elif comment_denial:
        decisive, status = comment_denial[-1], "denied"
    elif set(markers).issubset({item.marker for item in comment_direct}):
        decisive, status = comment_direct[-1], "affirmed"
    elif mentions:
        decisive = mentions[-1]
        status = "pending" if any(item.pending for item in mentions) else "other_actor" if any(
            item.reader_actor == "other" for item in mentions
        ) else "reported"
    return EditionCurrentRelation(
        candidate_title=candidate_title, markers=markers, status=status,
        basis=decisive.basis if status == "affirmed" and decisive else "",
        source_role=decisive.source_role if decisive else "unknown",
        source_index=decisive.source_index if decisive else 0,
        evidence_span=decisive.evidence_span if decisive else (0, 0),
        record_role_provenance=ledger.record_role_provenance,
        native_reduction={
            "call_path":"_edition_current_relation_from_ledger",
            "candidate_title_input":candidate_title,
            "candidate_marker_input":markers,
            "selected_mention_ids":tuple(m.mention_id for m in ledger.work_mentions
                if m.work_id==_title_key(candidate_base) and m.marker in markers),
            "source_reductions":tuple(r for r in ledger.native_reductions if r['object_mention_id'] in {
                m.mention_id for m in ledger.work_mentions if m.work_id==_title_key(candidate_base) and m.marker in markers}),
            "post_names_candidate":post_names_candidate,"status":status,
            "rule":"author_denial_survives_until_later_author_read_then_author_before_comment",
            "final_publication":"NOT_OBSERVED",
        },
    )


def edition_current_relation_with_record_roles(
    sources: Iterable[Tuple[str, Any]], candidate_title: str, *,
    producer, product_binding, typed_binding,
):
    """명시적 producer packet만 받는 opt-in 후보 API; 기존 호출은 바뀌지 않는다."""
    chunks = tuple(sources)
    base_ledger = _edition_source_ledger(chunks)
    session = prepare_pass(base_ledger, producer, product_binding, typed_binding)
    relation = _edition_current_relation_from_ledger(
        session.ledger, chunks, candidate_title, record_role_session=session)
    return bind_return(session, relation)


def edition_markers_in_text(value: Any) -> Tuple[str, ...]:
    """Extract bracketed edition markers from original post text."""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return tuple(
        dict.fromkeys(match.group(1).casefold() for match in _EDITION_MARKER_RE.finditer(normalized))
    )


def edition_markers_for_candidate_in_text(value: Any, candidate_title: str) -> Tuple[str, ...]:
    """Compatibility wrapper for a single original-text source."""
    return edition_markers_for_candidate_from_sources((("post_body", value),), candidate_title)


def _competing_edition_variant(candidate_title: str, titles: Iterable[str]) -> bool:
    candidate_title = unicodedata.normalize("NFKC", candidate_title)
    candidate_base = _title_key(_EDITION_MARKER_RE.sub("", candidate_title))
    candidate_key = _title_key(candidate_title)
    if not candidate_base:
        return False
    return any(
        _title_key(
            _EDITION_MARKER_RE.sub("", unicodedata.normalize("NFKC", str(title or "")))
        ) == candidate_base
        and _title_key(title) != candidate_key
        for title in titles
    )


def _canonical_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return text.rstrip("/").lower()
    if not parts.scheme or not parts.netloc:
        return text.rstrip("/").lower()
    path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/") or "/"
    semantic_query = sorted(
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    )
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(semantic_query, doseq=True),
            "",
        )
    )


def _record_url(record: EvidenceRecord) -> str:
    explicit = str(record.candidate_url or "").strip()
    if explicit:
        return explicit
    source = str(record.source_path_or_snippet or "").strip()
    return source if source.startswith(("http://", "https://")) else ""


def _supported_official_work_url(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parts = urlsplit(text)
    except ValueError:
        return False
    host = parts.netloc.lower().split(":", 1)[0]
    path = parts.path or ""
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if parts.scheme.lower() not in {"http", "https"}:
        return False
    if host.endswith("novelpia.com"):
        return bool(re.search(r"/novel/\d+(?:/|$)", path))
    if host == "series.naver.com":
        return path.rstrip("/") == "/novel/detail.series" and bool(query.get("productNo"))
    if "page.kakao.com" in host or "kakao.page" in host:
        from llm_batch.kakao_routes import is_kakao_work_detail_url
        return is_kakao_work_detail_url(text)
    if host in {"www.munpia.com", "munpia.com"}:
        # Desktop work routes must satisfy the same narrow identity contract
        # as final-pair selection. Do not broaden the legacy mobile routes.
        try:
            if parts.username is not None or parts.password is not None or parts.port is not None or parts.fragment:
                return False
        except ValueError:
            return False
        desktop_pairs = parse_qsl(parts.query, keep_blank_values=True)
        desktop_query = dict(desktop_pairs)
        if len(desktop_query) != len(desktop_pairs):
            return False
        if any(key != "ref" and not key.startswith("utm_") for key in desktop_query):
            return False
        return bool(re.fullmatch(r"/novel/detail/[1-9][0-9]*/?", path))
    if host in {"novel.munpia.com", "m.munpia.com", "mm.munpia.com"}:
        return bool(
            re.search(r"/(?:novel/detail/)?\d+(?:/|$)", path)
            or query.get("id", "").isdigit()
        )
    if host.endswith("ridibooks.com"):
        return bool(re.search(r"/books/\d+(?:/|$)", path))
    if host.endswith("joara.com"):
        return bool(re.search(r"/(?:book|novel|series)/", path, flags=re.IGNORECASE))
    return False


def _record_bound_to_candidate(
    state: GroundingState,
    record: EvidenceRecord,
    *,
    require_title: bool,
) -> bool:
    candidate_title = _title_key(state.candidate_title)
    record_title = _title_key(record.candidate_title)
    if record_title and record_title != candidate_title:
        return False
    if require_title and not record_title:
        source_title = _title_key(record.source_path_or_snippet)
        if not source_title or source_title != candidate_title:
            return False

    candidate_url = _canonical_url(state.candidate_url)
    record_url = _canonical_url(_record_url(record))
    if record_url and candidate_url and record_url != candidate_url:
        return False
    return bool(record_title or record_url or (not require_title and record.title_url_match is not None))


def _title_url_pair_status(
    state: GroundingState,
    records: Iterable[EvidenceRecord],
) -> str:
    """Return verified, mismatch, missing, or not_applicable for the candidate pair."""
    candidate_url = _canonical_url(state.candidate_url)
    if not candidate_url:
        return "not_applicable"
    if not _supported_official_work_url(state.candidate_url):
        return "untrusted"
    candidate_title = _title_key(state.candidate_title)
    verified = False
    for record in records:
        record_url = _canonical_url(_record_url(record))
        record_title = _title_key(record.candidate_title)
        if record_title and record_title != candidate_title:
            continue
        if record_url and record_url != candidate_url:
            continue
        if record.title_url_match is False:
            if _record_bound_to_candidate(state, record, require_title=False):
                return "mismatch"
            continue
        if (
            record.title_url_match is True
            and record_url == candidate_url
            and record_title == candidate_title
        ):
            verified = True
    return "verified" if verified else "missing"


def scope_state_from_dict(value: Any) -> Optional[ScopeState]:
    if isinstance(value, ScopeState):
        return value
    if not isinstance(value, Mapping):
        return None
    return ScopeState(
        scope_kind=str(value.get("scope_kind") or "unknown"),
        confidence=str(value.get("confidence") or "medium"),
        direct_bridge_sources=[
            str(item) for item in (value.get("direct_bridge_sources") or []) if str(item).strip()
        ],
        competing_candidates=[
            str(item) for item in (value.get("competing_candidates") or []) if str(item).strip()
        ],
        conflict_reason_codes=[
            str(item) for item in (value.get("conflict_reason_codes") or []) if str(item).strip()
        ],
    )


def retrieval_state_from_dict(value: Any) -> Optional[RetrievalState]:
    if isinstance(value, RetrievalState):
        return value
    if not isinstance(value, Mapping):
        return None
    def strict_bool(field_name: str) -> bool:
        field_value = value.get(field_name, False)
        if not isinstance(field_value, bool):
            raise ValueError(f"retrieval.{field_name} must be a bool")
        return field_value

    reason_codes = value.get("reason_codes", ())
    if not isinstance(reason_codes, (list, tuple)):
        raise ValueError("retrieval.reason_codes must be a list or tuple")
    return RetrievalState(
        required=strict_bool("required"),
        attempted=strict_bool("attempted"),
        recovered=strict_bool("recovered"),
        hard_blocked=strict_bool("hard_blocked"),
        reason_codes=tuple(str(item) for item in reason_codes if str(item).strip()),
    )


def semantic_publication_state_from_dict(
    value: Any,
) -> Optional[SemanticPublicationState]:
    if isinstance(value, SemanticPublicationState):
        return value
    if not isinstance(value, Mapping):
        return None
    allowed_fields = {
        "evidence_status",
        "media_domain_class",
        "primary_work_status",
    }
    unexpected = set(value) - allowed_fields
    if unexpected:
        raise ValueError(
            "semantic_publication fields mismatch: "
            f"extra={sorted(str(item) for item in unexpected)}"
        )
    for field_name in allowed_fields:
        field_value = value.get(field_name, "")
        if not isinstance(field_value, str):
            raise ValueError(f"semantic_publication.{field_name} must be a string")
    return SemanticPublicationState(
        evidence_status=value.get("evidence_status", ""),
        media_domain_class=value.get("media_domain_class", ""),
        primary_work_status=value.get("primary_work_status", ""),
    )


def edition_current_relation_from_dict(value: Any) -> Optional[EditionCurrentRelation]:
    if isinstance(value, EditionCurrentRelation):
        return value
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("edition current relation must be a mapping")
    required = {
        "candidate_title", "markers", "status", "basis", "source_role",
        "source_index", "evidence_span",
    }
    if set(value) != required:
        raise ValueError("edition current relation fields mismatch")
    markers, span = value["markers"], value["evidence_span"]
    if not isinstance(markers, (list, tuple)) or not isinstance(span, (list, tuple)):
        raise ValueError("edition current relation markers/span must be sequences")
    return EditionCurrentRelation(
        candidate_title=value["candidate_title"], markers=tuple(markers),
        status=value["status"], basis=value["basis"],
        source_role=value["source_role"], source_index=value["source_index"],
        evidence_span=tuple(span),
    )


def edition_publication_state_from_dict(value: Any) -> Optional[EditionPublicationState]:
    if isinstance(value, EditionPublicationState):
        return value
    if not isinstance(value, Mapping):
        return None
    allowed_fields = {
        "source_checked",
        "explicit_edition_markers",
        "competing_variant_titles",
        "current_relation",
    }
    unexpected = set(value) - allowed_fields
    if unexpected:
        raise ValueError(
            "edition_publication fields mismatch: "
            f"extra={sorted(str(item) for item in unexpected)}"
        )
    source_checked = value.get("source_checked", False)
    if not isinstance(source_checked, bool):
        raise ValueError("edition_publication.source_checked must be a bool")
    markers = value.get("explicit_edition_markers", ())
    variants = value.get("competing_variant_titles", ())
    if not isinstance(markers, (list, tuple)) or not isinstance(variants, (list, tuple)):
        raise ValueError("edition_publication marker and variant fields must be sequences")
    if any(not isinstance(item, str) for item in (*markers, *variants)):
        raise ValueError("edition_publication marker and variant values must be strings")
    return EditionPublicationState(
        source_checked=source_checked,
        explicit_edition_markers=tuple(markers),
        competing_variant_titles=tuple(variants),
        current_relation=edition_current_relation_from_dict(value.get("current_relation")),
    )


def grounding_state_from_dict(value: Any) -> GroundingState:
    payload = value if isinstance(value, Mapping) else {}
    post_id = payload.get("post_id")
    try:
        normalized_post_id = int(post_id) if post_id not in (None, "") else None
    except (TypeError, ValueError):
        normalized_post_id = None
    return GroundingState(
        post_id=normalized_post_id,
        candidate_title=str(payload.get("candidate_title") or ""),
        candidate_url=str(payload.get("candidate_url") or ""),
        source=str(payload.get("source") or "title_promotion"),
        official_title_exists=payload.get("official_title_exists") is True,
        row_discusses_work_as_work=payload.get("row_discusses_work_as_work") is True,
        title_resolution_state=str(payload.get("title_resolution_state") or ""),
        work_resolution=str(payload.get("work_resolution") or ""),
        discussion_type=str(payload.get("discussion_type") or ""),
        prior_variance_quarantine=payload.get("prior_variance_quarantine") is True,
        same_title_source_movement=payload.get("same_title_source_movement") is True,
        caveated_alias_boundary=payload.get("caveated_alias_boundary") is True,
        candidate_inventory_count=_nonnegative_int(payload.get("candidate_inventory_count")),
        scope=scope_state_from_dict(payload.get("scope")),
        retrieval=retrieval_state_from_dict(payload.get("retrieval")),
        semantic_publication=semantic_publication_state_from_dict(
            payload.get("semantic_publication")
        ),
        edition_publication=edition_publication_state_from_dict(
            payload.get("edition_publication")
        ),
    )


def evidence_records_from_payload(value: Any) -> Tuple[EvidenceRecord, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    records: List[EvidenceRecord] = []
    for item in value:
        if isinstance(item, EvidenceRecord):
            records.append(item)
            continue
        if not isinstance(item, Mapping):
            continue
        title_url_match = item.get("title_url_match")
        records.append(
            EvidenceRecord(
                kind=str(item.get("kind") or ""),
                strength=str(item.get("strength") or "medium"),
                source_path_or_snippet=str(item.get("source_path_or_snippet") or ""),
                supports_publish=item.get("supports_publish") is True,
                reason_code=str(item.get("reason_code") or ""),
                candidate_title=str(item.get("candidate_title") or ""),
                candidate_url=str(item.get("candidate_url") or ""),
                title_url_match=title_url_match if isinstance(title_url_match, bool) else None,
            )
        )
    return tuple(records)


def candidate_inventory_evidence_from_sources(*sources: Any) -> Tuple[EvidenceRecord, ...]:
    """Build deterministic preservation-only evidence for an unselected inventory.

    Inventory evidence can change only candidate-preservation bookkeeping.  It
    never supports publication and never chooses a representative candidate.
    """

    records: List[EvidenceRecord] = []
    seen: set[tuple[str, str]] = set()

    def _iter_items(value: Any) -> Iterable[Any]:
        if isinstance(value, (list, tuple)):
            for item in value:
                yield item
        elif value not in (None, ""):
            yield value

    for source in sources:
        for item in _iter_items(source):
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
            elif isinstance(item, str):
                title = item.strip()
                url = ""
            else:
                continue
            if not title and not url:
                continue
            key = (_title_key(title), _canonical_url(url))
            if key in seen:
                continue
            seen.add(key)
            records.append(
                EvidenceRecord(
                    kind="candidate_preservation",
                    strength="medium",
                    source_path_or_snippet=title or url,
                    supports_publish=False,
                    reason_code="candidate_inventory_preserved_without_selection",
                    candidate_title=title,
                    candidate_url=url,
                )
            )
    return tuple(records)


def candidate_inventory_records(
    evidence: Optional[Iterable[EvidenceRecord]],
) -> Tuple[EvidenceRecord, ...]:
    """Return unique typed inventory records, excluding publish evidence."""

    records: List[EvidenceRecord] = []
    seen: set[tuple[str, str]] = set()
    for record in evidence or ():
        if not isinstance(record, EvidenceRecord) or record.kind != "candidate_preservation":
            continue
        if record.supports_publish:
            continue
        title = str(record.candidate_title or "").strip()
        url = str(record.candidate_url or "").strip()
        if not title and not url:
            continue
        key = (_title_key(title), _canonical_url(url))
        if key in seen:
            continue
        seen.add(key)
        records.append(record)
    return tuple(records)


def candidate_inventory_pairs(
    evidence: Optional[Iterable[EvidenceRecord]],
) -> frozenset[tuple[str, str]]:
    """Return the exact reader-facing title/URL inventory represented by evidence."""

    return frozenset(
        (
            str(record.candidate_title or "").strip(),
            str(record.candidate_url or "").strip(),
        )
        for record in candidate_inventory_records(evidence)
    )


def normalize_blocked_resolution_state(
    title_resolution_state: Any,
    work_resolution: Any,
) -> Tuple[str, str, bool]:
    """Normalize non-publishing candidate state away from resolved semantics.

    A fail-closed publish decision may preserve candidates, but it must not
    serialize a public-null row as title/work ``resolved``.  Serializer,
    rescue, and late mismatch paths share this helper so none can bypass the
    same state transition.
    """

    title_state = str(title_resolution_state or "").strip()
    work_state = str(work_resolution or "").strip()
    changed = False
    if title_state.lower() == "resolved":
        title_state = "unresolved_matchable"
        changed = True
    if work_state.lower() == "resolved":
        work_state = "unresolved"
        changed = True
    return title_state, work_state, changed


def can_publish_title(
    state: GroundingState,
    evidence: Optional[Iterable[EvidenceRecord]] = None,
) -> PromotionDecision:
    """Return a contract-testable public title promotion decision."""
    records = tuple(record for record in (evidence or []) if isinstance(record, EvidenceRecord))
    input_fingerprint = publish_input_fingerprint(state, records)
    evidence_codes = [
        record.reason_code
        for record in records
        if str(record.reason_code or "").strip()
    ]
    reason_codes = _dedupe([*_state_reason_codes(state), *evidence_codes])

    candidate_title = str(state.candidate_title or "").strip()
    candidate_url = str(state.candidate_url or "").strip()
    if not candidate_title:
        inventory_count = _nonnegative_int(state.candidate_inventory_count)
        inventory_records = candidate_inventory_records(records)
        if candidate_url and not inventory_count and not inventory_records:
            return PromotionDecision(
                status="candidate_only",
                publish_allowed=False,
                official_title=None,
                official_url=None,
                candidate_preserved=True,
                reason_codes=_dedupe(
                    [
                        "no_public_candidate_title",
                        "candidate_url_preserved_without_title",
                        *reason_codes,
                    ]
                ),
                bypassed_gate=False,
                scope=state.scope,
                input_fingerprint=input_fingerprint,
            )
        if inventory_count > 0 and len(inventory_records) == inventory_count:
            return PromotionDecision(
                status="candidate_only",
                publish_allowed=False,
                official_title=None,
                official_url=None,
                candidate_preserved=True,
                reason_codes=_dedupe(
                    [
                        "no_public_candidate_title",
                        "candidate_inventory_preserved_without_selection",
                        *reason_codes,
                    ]
                ),
                bypassed_gate=False,
                scope=state.scope,
                input_fingerprint=input_fingerprint,
            )
        inventory_mismatch = bool(inventory_count or inventory_records)
        return PromotionDecision(
            status="reject",
            publish_allowed=False,
            official_title=None,
            official_url=None,
            candidate_preserved=False,
            reason_codes=_dedupe(
                [
                    "no_candidate_title",
                    *(["candidate_inventory_evidence_mismatch"] if inventory_mismatch else []),
                    *reason_codes,
                ]
            ),
            bypassed_gate=False,
            scope=state.scope,
            input_fingerprint=input_fingerprint,
        )

    supports_publish = any(
        record.supports_publish
        and _record_bound_to_candidate(state, record, require_title=True)
        for record in records
    )
    blocking_reasons = BLOCKING_REASON_CODES.intersection(reason_codes)
    hard_blocking_reasons = HARD_BLOCKING_REASON_CODES.intersection(reason_codes)
    contract_blocking_reasons = CONTRACT_BLOCKING_REASON_CODES.intersection(reason_codes)
    scope_kind = state.scope.normalized_kind() if isinstance(state.scope, ScopeState) else "unknown"
    direct_bridge_sources = (
        _dedupe(state.scope.direct_bridge_sources)
        if isinstance(state.scope, ScopeState)
        else []
    )
    scope_blocks_publish = scope_kind != SCOPE_CURRENT_WORK
    if scope_kind == SCOPE_CURRENT_WORK and not direct_bridge_sources:
        reason_codes = _dedupe([*reason_codes, "direct_bridge_missing"])
        scope_blocks_publish = True
    pair_status = _title_url_pair_status(state, records)
    if candidate_url and pair_status == "verified":
        reason_codes = _dedupe([*reason_codes, "title_url_pair_verified"])
    elif candidate_url and pair_status == "mismatch":
        reason_codes = _dedupe([*reason_codes, "official_url_withheld_by_title_mismatch"])
    elif candidate_url and pair_status == "untrusted":
        reason_codes = _dedupe([*reason_codes, "official_url_untrusted"])
    elif candidate_url:
        reason_codes = _dedupe([*reason_codes, "official_url_evidence_missing"])
    edition_blocked = False
    edition_state = state.edition_publication
    candidate_markers = edition_markers_in_text(candidate_title)
    if candidate_markers:
        relation = (
            edition_state.current_relation
            if isinstance(edition_state, EditionPublicationState) else None
        )
        relation_affirmed = bool(
            isinstance(edition_state, EditionPublicationState)
            and edition_state.source_checked
            and isinstance(relation, EditionCurrentRelation)
            and _title_key(relation.candidate_title) == _title_key(candidate_title)
            and set(candidate_markers) == set(relation.markers)
            and relation.status == "affirmed"
            and relation.basis in {
                "author_read", "author_identify", "current_post_record", "bound_comment_identify",
            }
        )
        if not relation_affirmed:
            edition_blocked = True
            reason_codes = _dedupe([*reason_codes, "edition_current_relation_unverified"])
    if (
        isinstance(edition_state, EditionPublicationState)
        and edition_state.source_checked
        and candidate_markers
        and not set(candidate_markers).issubset(
            {str(marker).casefold() for marker in edition_state.explicit_edition_markers}
        )
    ):
        exact_active_detail = bool(
            pair_status == "verified"
            and candidate_url
            and any(
                record.reason_code == "official_detail_display_title_exact"
                and record.title_url_match is True
                and _title_key(record.candidate_title) == _title_key(candidate_title)
                and _canonical_url(_record_url(record)) == _canonical_url(candidate_url)
                for record in records
            )
        )
        binding_unavailable = any(
            record.reason_code == "official_detail_display_binding_unavailable"
            and _record_bound_to_candidate(state, record, require_title=True)
            for record in records
        )
        competing_variant = _competing_edition_variant(
            candidate_title, edition_state.competing_variant_titles
        )
        legacy_marker_blocked = bool(
            not exact_active_detail and (binding_unavailable or competing_variant)
        )
        edition_blocked = edition_blocked or legacy_marker_blocked
        if legacy_marker_blocked:
            reason_codes = _dedupe([*reason_codes, "unverified_edition_title_only"])
    if state.prior_variance_quarantine or state.same_title_source_movement:
        status = "quarantine"
    elif scope_blocks_publish:
        status = "candidate_only"
    elif edition_blocked:
        status = "candidate_only"
    elif contract_blocking_reasons:
        status = "candidate_only"
    elif hard_blocking_reasons and not state.row_discusses_work_as_work:
        status = "candidate_only"
    elif state.row_discusses_work_as_work and supports_publish:
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
        official_url=(
            candidate_url
            if publish_allowed and candidate_url and pair_status == "verified"
            else None
        ),
        candidate_preserved=not publish_allowed,
        reason_codes=reason_codes,
        bypassed_gate=False,
        scope=state.scope,
        input_fingerprint=input_fingerprint,
    )


def evaluate_publish_contract(
    state: GroundingState,
    evidence: Optional[Iterable[EvidenceRecord]] = None,
    *,
    post_gate_context: Optional[Mapping[str, Any]] = None,
) -> PublishContract:
    """Evaluate one immutable state/evidence contract and build its trace.

    ``post_gate_context`` is retained for call-site compatibility only.  A
    serialized trace or identity is output, not publication evidence, so it
    must never influence the deterministic post-gate identity.
    """
    records = tuple(record for record in (evidence or []) if isinstance(record, EvidenceRecord))
    original_records = records
    working_state = state
    decision = can_publish_title(working_state, records)
    if not decision.publish_allowed:
        title_state, work_state, normalized_resolution = normalize_blocked_resolution_state(
            working_state.title_resolution_state,
            working_state.work_resolution,
        )
        if normalized_resolution:
            working_state = replace(
                working_state,
                title_resolution_state=title_state,
                work_resolution=work_state,
            )
            if not any(
                record.reason_code == "blocked_candidate_resolution_state_normalized"
                for record in records
            ):
                records = (
                    *records,
                    EvidenceRecord(
                        kind="blocked_candidate_resolution_state_normalized",
                        strength="strong",
                        source_path_or_snippet=(
                            working_state.candidate_title
                            or working_state.source
                            or "nonpublishing_contract"
                        ),
                        supports_publish=False,
                        reason_code="blocked_candidate_resolution_state_normalized",
                        candidate_title=working_state.candidate_title,
                        candidate_url=working_state.candidate_url,
                    ),
                )
            decision = can_publish_title(working_state, records)
    _ = post_gate_context
    pre_gate_candidate = PublishIdentity(
        official_title=str(working_state.candidate_title or "").strip() or None,
        official_url=str(working_state.candidate_url or "").strip() or None,
    )
    post_gate_identity = PublishIdentity(
        official_title=decision.official_title if decision.publish_allowed else None,
        official_url=decision.official_url if decision.publish_allowed else None,
        title_resolution_allowed=decision.publish_allowed,
        title_resolution_state=(
            str(working_state.title_resolution_state or "").strip()
            or None
        ),
        work_resolution=(
            str(working_state.work_resolution or "").strip()
            or None
        ),
        candidate_ledger_status=(
            "safe_resolved"
            if decision.publish_allowed
            else "promotion_blocked"
            if (
                pre_gate_candidate.official_title
                or pre_gate_candidate.official_url
                or decision.candidate_preserved
            )
            else "hold_without_candidates"
        ),
    )
    trace = PublishContractTrace(
        pre_gate_candidate=pre_gate_candidate,
        gate_decision=decision,
        scope_state=working_state.scope,
        post_gate_identity=post_gate_identity,
        reason_codes=tuple(decision.reason_codes),
        input_fingerprint=decision.input_fingerprint,
    )
    return PublishContract(
        state=working_state,
        evidence=records,
        decision=decision,
        trace=trace,
        input_fingerprint=decision.input_fingerprint,
        native_input_trace={
            "call_path":"evaluate_publish_contract -> can_publish_title",
            "input_type":type(state).__module__+"."+type(state).__qualname__,
            "typed_input":state.to_dict(),
            "evidence_input":tuple(record.to_dict() for record in original_records),
            "effective_evidence":tuple(record.to_dict() for record in records),
            "current_edition_authority":asdict(state.edition_publication.current_relation)
                if state.edition_publication and state.edition_publication.current_relation else "NOT_OBSERVED",
            "final_publication_allowed":decision.publish_allowed,
            "final_reason_codes":decision.reason_codes,
            "effective_input_fingerprint":decision.input_fingerprint,
        },
    )


def apply_publish_contract(
    identity: MutableMapping[str, Any],
    contract: PublishContract,
) -> MutableMapping[str, Any]:
    """Apply the sole public title/URL writer contract to a serialized identity."""
    if not isinstance(contract, PublishContract):
        raise TypeError("apply_publish_contract requires a typed PublishContract")

    decision = contract.decision
    decision_payload = decision.to_dict()
    state_payload = contract.state.to_dict()
    evidence_payload = [record.to_dict() for record in contract.evidence]
    trace_payload = contract.trace.to_dict()
    publish_ledger = build_publish_ledger(trace_payload)

    public_title_keys = ("official_title", "official_novel_title", "resolved_title")
    public_url_keys = ("heretic_url", "official_url", "resolved_url")

    for key in public_title_keys:
        if key in identity:
            identity[key] = decision.official_title if decision.publish_allowed else None
    for key in public_url_keys:
        if key in identity:
            identity[key] = decision.official_url if decision.publish_allowed else None

    novel_identity = identity.get("novel_identity")
    if not isinstance(novel_identity, MutableMapping):
        novel_identity = {}
    else:
        novel_identity = dict(novel_identity)
    if decision.publish_allowed:
        novel_identity["official_title"] = decision.official_title
        novel_identity["heretic_url"] = decision.official_url
        if "official_url" in novel_identity:
            novel_identity["official_url"] = decision.official_url
        if "resolved_title" in novel_identity:
            novel_identity["resolved_title"] = decision.official_title
        if "resolved_url" in novel_identity:
            novel_identity["resolved_url"] = decision.official_url
        identity.pop("blocked_official_title", None)
        identity.pop("blocked_official_title_url", None)
    else:
        for key in public_title_keys:
            if key == "official_title" or key in novel_identity:
                novel_identity[key] = None
        for key in public_url_keys:
            if key == "heretic_url" or key in novel_identity:
                novel_identity[key] = None
        if contract.state.candidate_title:
            identity["blocked_official_title"] = contract.state.candidate_title
        if contract.state.candidate_url:
            identity["blocked_official_title_url"] = contract.state.candidate_url
    identity["novel_identity"] = novel_identity or None

    identity["promotion_decision"] = decision_payload
    identity["promotion_gate_state"] = state_payload
    identity["promotion_gate_evidence"] = evidence_payload
    identity["publish_contract_trace"] = trace_payload
    identity["publish_ledger"] = publish_ledger
    identity["publish_contract_input_fingerprint"] = contract.input_fingerprint
    identity["publish_contract_version"] = contract.contract_version
    identity["title_resolution_allowed"] = contract.trace.post_gate_identity.title_resolution_allowed
    identity["title_resolution_state"] = contract.trace.post_gate_identity.title_resolution_state
    identity["work_resolution"] = contract.trace.post_gate_identity.work_resolution

    ledger = identity.get("candidate_ledger")
    ledger = dict(ledger) if isinstance(ledger, Mapping) else {}
    ledger["promotion_decision"] = decision_payload
    ledger["promotion_gate_state"] = state_payload
    ledger["promotion_gate_evidence"] = evidence_payload
    ledger["publish_contract_trace"] = trace_payload
    ledger["publish_ledger"] = publish_ledger
    ledger["publish_contract_input_fingerprint"] = contract.input_fingerprint
    ledger["publish_contract_version"] = contract.contract_version
    ledger["candidate_ledger_status"] = contract.trace.post_gate_identity.candidate_ledger_status
    ledger["title_resolution_allowed"] = contract.trace.post_gate_identity.title_resolution_allowed
    ledger["title_resolution_state"] = contract.trace.post_gate_identity.title_resolution_state
    ledger["work_resolution"] = contract.trace.post_gate_identity.work_resolution
    if decision.publish_allowed:
        ledger.pop("blocked_official_title", None)
        ledger.pop("blocked_official_title_url", None)
    else:
        if contract.state.candidate_title:
            ledger["blocked_official_title"] = contract.state.candidate_title
        if contract.state.candidate_url:
            ledger["blocked_official_title_url"] = contract.state.candidate_url
    identity["candidate_ledger"] = ledger
    identity["candidate_ledger_status"] = contract.trace.post_gate_identity.candidate_ledger_status
    status = str(contract.trace.post_gate_identity.candidate_ledger_status or "")
    identity["promotion_blocked"] = status == "promotion_blocked"
    identity["hold_without_candidates"] = status == "hold_without_candidates"
    identity["safe_resolved"] = status == "safe_resolved"
    ledger["promotion_blocked"] = status == "promotion_blocked"
    ledger["hold_without_candidates"] = status == "hold_without_candidates"
    ledger["safe_resolved"] = status == "safe_resolved"
    identity["candidate_ledger"] = ledger
    return identity


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, (PromotionDecision, PublishIdentity, PublishContractTrace, PublishContract)):
        return value.to_dict()
    if isinstance(value, ScopeState):
        return value.to_dict()
    if isinstance(value, GroundingState):
        return value.to_dict()
    return dict(value) if isinstance(value, dict) else {}


def build_publish_contract_trace(
    decision: PromotionDecision | Dict[str, Any],
    *,
    scope_state: Optional[ScopeState | Dict[str, Any]] = None,
    pre_gate_candidate: Optional[Dict[str, Any]] = None,
    post_gate_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the shared trace payload for a PromotionDecision."""
    gate_decision = _as_dict(decision)
    gate_decision["bypassed_gate"] = False
    scope_payload = _as_dict(scope_state) or _as_dict(gate_decision.get("scope"))
    if scope_payload:
        gate_decision["scope"] = scope_payload
    scope_kind = str(scope_payload.get("scope_kind") or "").strip() if scope_payload else ""
    reason_codes = gate_decision.get("reason_codes")
    if isinstance(reason_codes, list):
        normalized = normalize_scope_reason_codes(
            [str(code) for code in reason_codes if str(code).strip()],
            scope_kind=scope_kind,
        )
    else:
        normalized = []
    gate_decision["reason_codes"] = normalized

    publish_allowed = gate_decision.get("publish_allowed") is True
    official_title = gate_decision.get("official_title") if publish_allowed else None
    official_url = gate_decision.get("official_url") if publish_allowed else None
    pre_gate = dict(pre_gate_candidate or {})
    pre_gate.setdefault("official_title", gate_decision.get("official_title"))
    pre_gate.setdefault("official_url", gate_decision.get("official_url"))

    post_context = dict(post_gate_context or {})
    post_gate_identity = {
        "official_title": official_title,
        "official_url": official_url,
        "title_resolution_allowed": post_context.get("title_resolution_allowed"),
        "title_resolution_state": post_context.get("title_resolution_state"),
        "work_resolution": post_context.get("work_resolution"),
        "candidate_ledger_status": post_context.get("candidate_ledger_status"),
    }
    return {
        "pre_gate_candidate": pre_gate,
        "gate_decision": gate_decision,
        "scope_state": scope_payload,
        "post_gate_identity": post_gate_identity,
        "reason_codes": normalized,
        "bypassed_gate": False,
    }


def build_publish_ledger(trace: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "candidate_preservation": _as_dict(trace.get("pre_gate_candidate")),
        "public_publish": _as_dict(trace.get("post_gate_identity")),
        "gate_decision": _as_dict(trace.get("gate_decision")),
    }
