"""공개 제목과 URL의 최종 승격을 단일화하는 공통 계약.

공식 작품이 실제로 존재한다는 사실과 현재 게시글에 공개해도 안전하다는 판단은
서로 다르다. 후보가 실재하더라도 게시글이 그 작품을 작품으로 다루지 않으면
candidate-only로 보존하고 공개 필드는 fail-close한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
    return normalize_scope_reason_codes(codes, scope_kind=scope_kind)


def _canonical_payload(value: Any) -> Any:
    if isinstance(
        value,
        (EvidenceRecord, ScopeState, GroundingState, RetrievalState, PromotionDecision),
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
    if host == "page.kakao.com":
        return bool(re.search(r"/content/\d+(?:/|$)", path))
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
    if state.prior_variance_quarantine or state.same_title_source_movement:
        status = "quarantine"
    elif scope_blocks_publish:
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
