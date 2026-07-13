"""Source-only, measurement-only early routing contracts.

The contracts in this module deliberately sit *before* AgenticPipeline provider
dispatch.  A source view cannot carry WAL decisions, labels, judge seeds,
slang/session state, retrieval results, VLM/OCR output, or expert output.  Those
objects may be supplied only to :func:`compare_early_route` after a decision is
already immutable.

The only cheap action in v1 is a deterministic NIL proposal.  It is an
attempt-local measurement sidecar, never a publication or CandidateSet writer.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple


POLICY_SCHEMA = "early_route_policy_v1"
SOURCE_VIEW_SCHEMA = "early_route_source_view_v1"
CHEAP_NIL_SCHEMA = "early_route_cheap_nil_proposal_v1"
DECISION_SCHEMA = "early_route_decision_v1"
COMPARISON_SCHEMA = "early_route_comparison_receipt_v1"

ARM_AFTER = "AFTER"
LANE_FULL = "FULL_EXPERT_REQUIRED"
LANE_CHEAP_NIL = "CHEAP_NIL_MEASUREMENT"
NIL_LABEL = "__NIL__"
ACTION_ASSERT_NIL = "ASSERT_NIL"

ACCURACY_NOT_ESTIMABLE = "NOT_ESTIMABLE"
FROZEN_TRUTH_NOT_AVAILABLE = "NOT_AVAILABLE"
FROZEN_TRUTH_VERIFIED = "FROZEN_ACTUAL_VERIFIED"

_SHA256_LENGTH = 64
_SOURCE_FORBIDDEN_TOKENS = (
    "wal",
    "decision",
    "truth",
    "judge_seed",
    "slang",
    "session",
    "search",
    "retrieval",
    "vlm",
    "ocr",
    "expert",
)

_TEXT_BLOCK_KINDS = frozenset({"text", "plain_text", "paragraph"})
_IMAGE_BLOCK_MARKERS = (
    "image",
    "img",
    "photo",
    "attachment",
    "media",
    "image_url",
    "src",
)
_POSTHOC_BLOCK_MARKERS = ("search", "retrieval", "evidence", "vlm", "ocr", "expert")
_QUOTE_CHARS = frozenset("\"'“”‘’«»‹›「」『』《》〈〉【】〔〕")
_MULTIWORK_SYMBOLS = frozenset({"/", "&", "↔", "⇔", "→", "←", "+"})
_URL_RE = re.compile(
    r"(?:https?://|www\.|(?:[a-z0-9-]+\.)+(?:com|net|org|io|kr|co\.kr)\b)",
    re.IGNORECASE,
)
_MASKING_RE = re.compile(r"(?:ㅁ\s*ㅁ|■\s*■|□\s*□|▇\s*▇|\*{2,}|[xX]{2,})")
_MULTIWORK_RE = re.compile(r"(?:\bvs\.?\b|비교|둘\s*중|작품\s*[대:]\s*작품)", re.IGNORECASE)
_EPISODE_RE = re.compile(r"(?:\d+\s*(?:화|회|편|챕터)|회차)", re.IGNORECASE)
_PLATFORM_RE = re.compile(r"(?:노벨피아|문피아|카카오페이지|시리즈|조아라|리디)", re.IGNORECASE)


def _canonical_payload(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _canonical_payload(value.to_dict())
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        owners: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if key in normalized:
                raise ValueError(
                    "mapping key collision after string normalization: "
                    f"{owners[key]!r} and {raw_key!r}"
                )
            owners[key] = raw_key
            normalized[key] = _canonical_payload(item)
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, (list, tuple)):
        return [_canonical_payload(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported canonical payload type: {type(value).__name__}")


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        _canonical_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_exact_keys(value: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    actual = set(value)
    expected_set = set(expected)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        extra = sorted(actual - expected_set)
        raise ValueError(f"{label} shape mismatch: missing={missing}, extra={extra}")


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_raw_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _require_sha256(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a sha256 hex digest")
    text = value.strip().lower()
    if len(text) != _SHA256_LENGTH or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError(f"{field_name} must be a sha256 hex digest")
    return text


def _require_nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative int")
    return value


def _require_positive_int(value: Any, field_name: str) -> int:
    parsed = _require_nonnegative_int(value, field_name)
    if parsed == 0:
        raise ValueError(f"{field_name} must be positive")
    return parsed


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be bool")
    return value


def _require_optional_text(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    return _require_text(value, field_name)


def _require_string_tuple(value: Any, field_name: str) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple of strings")
    return tuple(_require_raw_text(item, f"{field_name} item") for item in value)


def _require_sorted_unique_codes(value: Any, field_name: str) -> Tuple[str, ...]:
    values = _require_string_tuple(value, field_name)
    normalized = tuple(sorted({_require_text(item, f"{field_name} item") for item in values}))
    if values != normalized:
        raise ValueError(f"{field_name} must be sorted and unique")
    return normalized


@dataclass(frozen=True)
class EarlyRoutePolicyV1:
    policy_origin: str
    allowed_arm: str
    allowed_emotive_jamo: Tuple[str, ...]
    cheap_lane: str
    full_lane: str
    unknown_routes_full: bool
    public_action_applied: bool
    policy_sha256: str
    schema_version: str = POLICY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != POLICY_SCHEMA:
            raise ValueError("unsupported early-route policy schema")
        object.__setattr__(self, "policy_origin", _require_text(self.policy_origin, "policy_origin"))
        if self.allowed_arm != ARM_AFTER:
            raise ValueError("early-route policy is AFTER-only")
        jamo = tuple(self.allowed_emotive_jamo)
        if jamo != ("ㅋ", "ㅎ", "ㅠ", "ㅜ"):
            raise ValueError("allowed emotive jamo must match the pre-registered v1 set")
        if self.cheap_lane != LANE_CHEAP_NIL or self.full_lane != LANE_FULL:
            raise ValueError("early-route lane contract mismatch")
        if _require_bool(self.unknown_routes_full, "unknown_routes_full") is not True:
            raise ValueError("unknown evidence must route to full experts")
        if _require_bool(self.public_action_applied, "public_action_applied") is not False:
            raise ValueError("measurement policy must not apply a public action")
        _require_sha256(self.policy_sha256, "policy_sha256")
        if self.policy_sha256 != canonical_hash(self.payload_without_hash()):
            raise ValueError("early-route policy fingerprint mismatch")

    @classmethod
    def create(cls) -> "EarlyRoutePolicyV1":
        payload = {
            "schema_version": POLICY_SCHEMA,
            "policy_origin": "PRE_REGISTERED_SOURCE_ONLY_FAIL_CLOSED_V1",
            "allowed_arm": ARM_AFTER,
            "allowed_emotive_jamo": ["ㅋ", "ㅎ", "ㅠ", "ㅜ"],
            "cheap_lane": LANE_CHEAP_NIL,
            "full_lane": LANE_FULL,
            "unknown_routes_full": True,
            "public_action_applied": False,
        }
        return cls(
            policy_origin=payload["policy_origin"],
            allowed_arm=payload["allowed_arm"],
            allowed_emotive_jamo=tuple(payload["allowed_emotive_jamo"]),
            cheap_lane=payload["cheap_lane"],
            full_lane=payload["full_lane"],
            unknown_routes_full=payload["unknown_routes_full"],
            public_action_applied=payload["public_action_applied"],
            policy_sha256=canonical_hash(payload),
        )

    def payload_without_hash(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_origin": self.policy_origin,
            "allowed_arm": self.allowed_arm,
            "allowed_emotive_jamo": list(self.allowed_emotive_jamo),
            "cheap_lane": self.cheap_lane,
            "full_lane": self.full_lane,
            "unknown_routes_full": self.unknown_routes_full,
            "public_action_applied": self.public_action_applied,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_hash(), "policy_sha256": self.policy_sha256}

    @classmethod
    def from_dict(cls, value: Any) -> "EarlyRoutePolicyV1":
        if not isinstance(value, Mapping):
            raise ValueError("early-route policy must be an object")
        _require_exact_keys(value, cls.__dataclass_fields__, "early-route policy")
        return cls(
            **{**dict(value), "allowed_emotive_jamo": tuple(value["allowed_emotive_jamo"])}
        )


@dataclass(frozen=True)
class EarlyRouteSourceView:
    publication_scope_id: str
    pair_id: str
    arm: str
    input_index: int
    post_id: str
    source_input_sha256: str
    title: str
    text_blocks: Tuple[str, ...]
    comments: Tuple[str, ...]
    block_kinds: Tuple[str, ...]
    image_url_count: int
    image_inventory_sha256: str
    external_url_count: int
    external_url_inventory_sha256: str
    source_evidence_count: int
    source_evidence_sha256: str
    unknown_block_count: int
    input_truncated: bool
    parse_error_codes: Tuple[str, ...]
    source_view_sha256: str
    schema_version: str = SOURCE_VIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_VIEW_SCHEMA:
            raise ValueError("unsupported early-route source-view schema")
        object.__setattr__(
            self,
            "publication_scope_id",
            _require_sha256(self.publication_scope_id, "publication_scope_id"),
        )
        object.__setattr__(self, "pair_id", _require_text(self.pair_id, "pair_id"))
        if self.arm != ARM_AFTER:
            raise ValueError("early-route source view is AFTER-only")
        _require_positive_int(self.input_index, "input_index")
        object.__setattr__(self, "post_id", _require_text(self.post_id, "post_id"))
        object.__setattr__(
            self,
            "source_input_sha256",
            _require_sha256(self.source_input_sha256, "source_input_sha256"),
        )
        object.__setattr__(self, "title", _require_raw_text(self.title, "title"))
        object.__setattr__(self, "text_blocks", _require_string_tuple(self.text_blocks, "text_blocks"))
        object.__setattr__(self, "comments", _require_string_tuple(self.comments, "comments"))
        object.__setattr__(self, "block_kinds", _require_string_tuple(self.block_kinds, "block_kinds"))
        for field_name in (
            "image_url_count",
            "external_url_count",
            "source_evidence_count",
            "unknown_block_count",
        ):
            _require_nonnegative_int(getattr(self, field_name), field_name)
        for field_name in (
            "image_inventory_sha256",
            "external_url_inventory_sha256",
            "source_evidence_sha256",
            "source_view_sha256",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        _require_bool(self.input_truncated, "input_truncated")
        object.__setattr__(
            self,
            "parse_error_codes",
            _require_sorted_unique_codes(self.parse_error_codes, "parse_error_codes"),
        )
        if self.source_view_sha256 != canonical_hash(self.payload_without_hash()):
            raise ValueError("early-route source-view fingerprint mismatch")

    @classmethod
    def create(
        cls,
        *,
        publication_scope_id: str,
        pair_id: str,
        arm: str,
        input_index: int,
        post_id: Any,
        source_input_sha256: str,
        title: str,
        text_blocks: Sequence[str] = (),
        comments: Sequence[str] = (),
        block_kinds: Sequence[str] = (),
        image_url_count: int = 0,
        image_inventory_sha256: Optional[str] = None,
        external_url_count: int = 0,
        external_url_inventory_sha256: Optional[str] = None,
        source_evidence_count: int = 0,
        source_evidence_sha256: Optional[str] = None,
        unknown_block_count: int = 0,
        input_truncated: bool = False,
        parse_error_codes: Sequence[str] = (),
    ) -> "EarlyRouteSourceView":
        image_hash = image_inventory_sha256 or canonical_hash({"count": image_url_count})
        external_hash = external_url_inventory_sha256 or canonical_hash(
            {"count": external_url_count}
        )
        evidence_hash = source_evidence_sha256 or canonical_hash(
            {"count": source_evidence_count}
        )
        payload = {
            "schema_version": SOURCE_VIEW_SCHEMA,
            "publication_scope_id": publication_scope_id,
            "pair_id": pair_id,
            "arm": arm,
            "input_index": input_index,
            "post_id": str(post_id),
            "source_input_sha256": source_input_sha256,
            "title": title,
            "text_blocks": list(text_blocks),
            "comments": list(comments),
            "block_kinds": list(block_kinds),
            "image_url_count": image_url_count,
            "image_inventory_sha256": image_hash,
            "external_url_count": external_url_count,
            "external_url_inventory_sha256": external_hash,
            "source_evidence_count": source_evidence_count,
            "source_evidence_sha256": evidence_hash,
            "unknown_block_count": unknown_block_count,
            "input_truncated": input_truncated,
            "parse_error_codes": sorted(set(parse_error_codes)),
        }
        return cls(
            publication_scope_id=publication_scope_id,
            pair_id=pair_id,
            arm=arm,
            input_index=input_index,
            post_id=str(post_id),
            source_input_sha256=source_input_sha256,
            title=title,
            text_blocks=tuple(text_blocks),
            comments=tuple(comments),
            block_kinds=tuple(block_kinds),
            image_url_count=image_url_count,
            image_inventory_sha256=image_hash,
            external_url_count=external_url_count,
            external_url_inventory_sha256=external_hash,
            source_evidence_count=source_evidence_count,
            source_evidence_sha256=evidence_hash,
            unknown_block_count=unknown_block_count,
            input_truncated=input_truncated,
            parse_error_codes=tuple(sorted(set(parse_error_codes))),
            source_view_sha256=canonical_hash(payload),
        )

    def payload_without_hash(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "publication_scope_id": self.publication_scope_id,
            "pair_id": self.pair_id,
            "arm": self.arm,
            "input_index": self.input_index,
            "post_id": self.post_id,
            "source_input_sha256": self.source_input_sha256,
            "title": self.title,
            "text_blocks": list(self.text_blocks),
            "comments": list(self.comments),
            "block_kinds": list(self.block_kinds),
            "image_url_count": self.image_url_count,
            "image_inventory_sha256": self.image_inventory_sha256,
            "external_url_count": self.external_url_count,
            "external_url_inventory_sha256": self.external_url_inventory_sha256,
            "source_evidence_count": self.source_evidence_count,
            "source_evidence_sha256": self.source_evidence_sha256,
            "unknown_block_count": self.unknown_block_count,
            "input_truncated": self.input_truncated,
            "parse_error_codes": list(self.parse_error_codes),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_hash(), "source_view_sha256": self.source_view_sha256}

    @classmethod
    def from_dict(cls, value: Any) -> "EarlyRouteSourceView":
        if not isinstance(value, Mapping):
            raise ValueError("early-route source view must be an object")
        expected = set(cls.__dataclass_fields__)
        extra = set(value) - expected
        forbidden = sorted(
            str(key)
            for key in extra
            if any(token in str(key).casefold() for token in _SOURCE_FORBIDDEN_TOKENS)
        )
        if forbidden:
            raise ValueError(f"forbidden source-view fields: {forbidden}")
        _require_exact_keys(value, expected, "early-route source view")
        return cls(
            **{
                **dict(value),
                "text_blocks": tuple(value["text_blocks"]),
                "comments": tuple(value["comments"]),
                "block_kinds": tuple(value["block_kinds"]),
                "parse_error_codes": tuple(value["parse_error_codes"]),
            }
        )


@dataclass(frozen=True)
class CheapNilProposal:
    terminal_action: str
    selected_label: str
    publish_allowed: bool
    official_title: None
    official_url: None
    candidate_ids: Tuple[()]
    public_action_applied: bool
    proposal_sha256: str
    schema_version: str = CHEAP_NIL_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != CHEAP_NIL_SCHEMA:
            raise ValueError("unsupported cheap NIL proposal schema")
        if self.terminal_action != ACTION_ASSERT_NIL or self.selected_label != NIL_LABEL:
            raise ValueError("cheap proposal must be deterministic NIL")
        if _require_bool(self.publish_allowed, "publish_allowed") is not False:
            raise ValueError("cheap NIL proposal cannot publish")
        if self.official_title is not None or self.official_url is not None:
            raise ValueError("cheap NIL proposal must keep public title and URL null")
        if tuple(self.candidate_ids):
            raise ValueError("cheap NIL proposal must not create CandidateSet entries")
        if _require_bool(self.public_action_applied, "public_action_applied") is not False:
            raise ValueError("cheap NIL proposal is measurement-only")
        _require_sha256(self.proposal_sha256, "proposal_sha256")
        if self.proposal_sha256 != canonical_hash(self.payload_without_hash()):
            raise ValueError("cheap NIL proposal fingerprint mismatch")

    @classmethod
    def create(cls) -> "CheapNilProposal":
        payload = {
            "schema_version": CHEAP_NIL_SCHEMA,
            "terminal_action": ACTION_ASSERT_NIL,
            "selected_label": NIL_LABEL,
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_ids": [],
            "public_action_applied": False,
        }
        return cls(
            terminal_action=ACTION_ASSERT_NIL,
            selected_label=NIL_LABEL,
            publish_allowed=False,
            official_title=None,
            official_url=None,
            candidate_ids=(),
            public_action_applied=False,
            proposal_sha256=canonical_hash(payload),
        )

    def payload_without_hash(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "terminal_action": self.terminal_action,
            "selected_label": self.selected_label,
            "publish_allowed": self.publish_allowed,
            "official_title": self.official_title,
            "official_url": self.official_url,
            "candidate_ids": list(self.candidate_ids),
            "public_action_applied": self.public_action_applied,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_hash(), "proposal_sha256": self.proposal_sha256}

    @classmethod
    def from_dict(cls, value: Any) -> "CheapNilProposal":
        if not isinstance(value, Mapping):
            raise ValueError("cheap NIL proposal must be an object")
        _require_exact_keys(value, cls.__dataclass_fields__, "cheap NIL proposal")
        return cls(**{**dict(value), "candidate_ids": tuple(value["candidate_ids"])})


@dataclass(frozen=True)
class EarlyRouteDecision:
    publication_scope_id: str
    pair_id: str
    arm: str
    input_index: int
    post_id: str
    source_view_sha256: str
    policy_sha256: str
    selected_lane: str
    hard_risk_codes: Tuple[str, ...]
    cheap_proposal: Optional[CheapNilProposal]
    provider_dispatch_allowed: bool
    compute_route_executed: bool
    public_action_applied: bool
    decision_sha256: str
    schema_version: str = DECISION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != DECISION_SCHEMA:
            raise ValueError("unsupported early-route decision schema")
        object.__setattr__(
            self,
            "publication_scope_id",
            _require_sha256(self.publication_scope_id, "publication_scope_id"),
        )
        object.__setattr__(self, "pair_id", _require_text(self.pair_id, "pair_id"))
        if self.arm != ARM_AFTER:
            raise ValueError("early-route decision is AFTER-only")
        _require_positive_int(self.input_index, "input_index")
        object.__setattr__(self, "post_id", _require_text(self.post_id, "post_id"))
        object.__setattr__(
            self, "source_view_sha256", _require_sha256(self.source_view_sha256, "source_view_sha256")
        )
        object.__setattr__(self, "policy_sha256", _require_sha256(self.policy_sha256, "policy_sha256"))
        if self.selected_lane not in {LANE_FULL, LANE_CHEAP_NIL}:
            raise ValueError("unsupported early-route lane")
        object.__setattr__(
            self,
            "hard_risk_codes",
            _require_sorted_unique_codes(self.hard_risk_codes, "hard_risk_codes"),
        )
        proposal = self.cheap_proposal
        if proposal is not None and not isinstance(proposal, CheapNilProposal):
            raise ValueError("cheap_proposal must be a CheapNilProposal or null")
        dispatch = _require_bool(self.provider_dispatch_allowed, "provider_dispatch_allowed")
        if self.selected_lane == LANE_CHEAP_NIL:
            if self.hard_risk_codes or proposal is None or dispatch:
                raise ValueError("cheap lane requires zero risks, a NIL proposal, and no provider dispatch")
        elif not self.hard_risk_codes or proposal is not None or not dispatch:
            raise ValueError("full lane requires risks, no proposal, and provider dispatch permission")
        if _require_bool(self.compute_route_executed, "compute_route_executed") is not True:
            raise ValueError("decision must record an executed compute route")
        if _require_bool(self.public_action_applied, "public_action_applied") is not False:
            raise ValueError("early-route decision must not apply a public action")
        _require_sha256(self.decision_sha256, "decision_sha256")
        if self.decision_sha256 != canonical_hash(self.payload_without_hash()):
            raise ValueError("early-route decision fingerprint mismatch")

    def payload_without_hash(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "publication_scope_id": self.publication_scope_id,
            "pair_id": self.pair_id,
            "arm": self.arm,
            "input_index": self.input_index,
            "post_id": self.post_id,
            "source_view_sha256": self.source_view_sha256,
            "policy_sha256": self.policy_sha256,
            "selected_lane": self.selected_lane,
            "hard_risk_codes": list(self.hard_risk_codes),
            "cheap_proposal": self.cheap_proposal.to_dict() if self.cheap_proposal else None,
            "provider_dispatch_allowed": self.provider_dispatch_allowed,
            "compute_route_executed": self.compute_route_executed,
            "public_action_applied": self.public_action_applied,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_hash(), "decision_sha256": self.decision_sha256}

    @classmethod
    def from_dict(cls, value: Any) -> "EarlyRouteDecision":
        if not isinstance(value, Mapping):
            raise ValueError("early-route decision must be an object")
        _require_exact_keys(value, cls.__dataclass_fields__, "early-route decision")
        raw_proposal = value["cheap_proposal"]
        proposal = CheapNilProposal.from_dict(raw_proposal) if raw_proposal is not None else None
        return cls(
            **{
                **dict(value),
                "hard_risk_codes": tuple(value["hard_risk_codes"]),
                "cheap_proposal": proposal,
            }
        )


def _normalized_text(source: EarlyRouteSourceView) -> str:
    joined = "\n".join((source.title, *source.text_blocks, *source.comments))
    # Normalize one source code point at a time.  Whole-string NFKC may compose
    # adjacent compatibility jamo (for example ㅎ+ㅠ) into a meaningful Hangul
    # syllable even though the source contained only repeated emotive tokens.
    return "".join(unicodedata.normalize("NFKC", char) for char in joined)


def _text_risks(text: str, policy: EarlyRoutePolicyV1) -> set[str]:
    risks: set[str] = set()
    if _URL_RE.search(text):
        risks.add("TEXT_URL_SIGNAL")
    if _MASKING_RE.search(text):
        risks.add("MASKING_SIGNAL")
    if any(char in _QUOTE_CHARS for char in text):
        risks.add("QUOTE_SIGNAL")
    if _MULTIWORK_RE.search(text) or any(char in _MULTIWORK_SYMBOLS for char in text):
        risks.add("MULTIWORK_SIGNAL")
    if _EPISODE_RE.search(text):
        risks.add("EPISODE_SIGNAL")
    if _PLATFORM_RE.search(text):
        risks.add("PLATFORM_SIGNAL")

    allowed_jamo = {
        unicodedata.normalize("NFKC", char)
        for char in policy.allowed_emotive_jamo
    }
    observed_jamo = 0
    for char in text:
        if char.isspace():
            continue
        category = unicodedata.category(char)
        if char in allowed_jamo:
            observed_jamo += 1
            continue
        if category[0] in {"P", "Z"}:
            continue
        if category[0] == "S":
            risks.add("SYMBOL_OR_EMOJI_SIGNAL")
            continue
        codepoint = ord(char)
        if 0xAC00 <= codepoint <= 0xD7A3:
            risks.add("MEANINGFUL_HANGUL_SYLLABLE")
        elif ("A" <= char <= "Z") or ("a" <= char <= "z"):
            risks.add("LATIN_SIGNAL")
        elif category[0] == "N":
            risks.add("DIGIT_SIGNAL")
        elif (
            0x1100 <= codepoint <= 0x11FF
            or 0x3130 <= codepoint <= 0x318F
            or 0xA960 <= codepoint <= 0xA97F
            or 0xD7B0 <= codepoint <= 0xD7FF
        ):
            risks.add("UNREGISTERED_JAMO_SIGNAL")
        elif category[0] == "L":
            risks.add("OTHER_LETTER_SIGNAL")
        elif category[0] == "C":
            risks.add("CONTROL_OR_FORMAT_SIGNAL")
        else:
            risks.add("UNRECOGNIZED_TEXT_SIGNAL")
    if observed_jamo == 1:
        risks.add("EMOTIVE_JAMO_NOT_REPEATED")
    return risks


def _derive_hard_risks(
    source: EarlyRouteSourceView,
    policy: EarlyRoutePolicyV1,
) -> Tuple[str, ...]:
    risks: set[str] = set()
    if source.arm != policy.allowed_arm:
        risks.add("ARM_NOT_AFTER")
    if source.image_url_count:
        risks.add("IMAGE_URL_PRESENT")
    if source.external_url_count:
        risks.add("EXTERNAL_URL_PRESENT")
    if source.source_evidence_count:
        risks.add("SOURCE_EVIDENCE_PRESENT")
    if source.unknown_block_count:
        risks.add("UNKNOWN_BLOCK_PRESENT")
    if source.input_truncated:
        risks.add("INPUT_TRUNCATED")
    if source.parse_error_codes:
        risks.add("SOURCE_PARSE_ERROR")
    for raw_kind in source.block_kinds:
        kind = unicodedata.normalize("NFKC", raw_kind).strip().casefold()
        if not kind:
            risks.add("UNKNOWN_BLOCK_KIND")
        elif any(marker in kind for marker in _IMAGE_BLOCK_MARKERS):
            risks.add("IMAGE_OR_ATTACHMENT_BLOCK")
        elif any(marker in kind for marker in _POSTHOC_BLOCK_MARKERS):
            risks.add("POSTHOC_EVIDENCE_BLOCK")
        elif kind not in _TEXT_BLOCK_KINDS:
            risks.add("UNKNOWN_BLOCK_KIND")
    risks.update(_text_risks(_normalized_text(source), policy))
    return tuple(sorted(risks))


def decide_early_route(
    source: EarlyRouteSourceView,
    policy: Optional[EarlyRoutePolicyV1] = None,
) -> EarlyRouteDecision:
    if not isinstance(source, EarlyRouteSourceView):
        raise TypeError("source must be an EarlyRouteSourceView")
    selected_policy = policy or EarlyRoutePolicyV1.create()
    if not isinstance(selected_policy, EarlyRoutePolicyV1):
        raise TypeError("policy must be an EarlyRoutePolicyV1")
    risks = _derive_hard_risks(source, selected_policy)
    lane = LANE_FULL if risks else LANE_CHEAP_NIL
    proposal = None if risks else CheapNilProposal.create()
    payload = {
        "schema_version": DECISION_SCHEMA,
        "publication_scope_id": source.publication_scope_id,
        "pair_id": source.pair_id,
        "arm": source.arm,
        "input_index": source.input_index,
        "post_id": source.post_id,
        "source_view_sha256": source.source_view_sha256,
        "policy_sha256": selected_policy.policy_sha256,
        "selected_lane": lane,
        "hard_risk_codes": list(risks),
        "cheap_proposal": proposal.to_dict() if proposal else None,
        "provider_dispatch_allowed": lane == LANE_FULL,
        "compute_route_executed": True,
        "public_action_applied": False,
    }
    return EarlyRouteDecision(
        publication_scope_id=source.publication_scope_id,
        pair_id=source.pair_id,
        arm=source.arm,
        input_index=source.input_index,
        post_id=source.post_id,
        source_view_sha256=source.source_view_sha256,
        policy_sha256=selected_policy.policy_sha256,
        selected_lane=lane,
        hard_risk_codes=risks,
        cheap_proposal=proposal,
        provider_dispatch_allowed=lane == LANE_FULL,
        compute_route_executed=True,
        public_action_applied=False,
        decision_sha256=canonical_hash(payload),
    )


@dataclass(frozen=True)
class EarlyRouteComparisonReceipt:
    publication_scope_id: str
    pair_id: str
    input_index: int
    post_id: str
    route_decision_sha256: str
    selected_lane: str
    authoritative_wal_receipt_sha256: str
    authoritative_wal_outcome: str
    baseline_equivalence_status: str
    baseline_equivalence_is_truth: bool
    public_projection_match: Optional[bool]
    public_projection_before_sha256: str
    public_projection_after_sha256: str
    public_noninterference_status: str
    frozen_truth_status: str
    frozen_truth_receipt_sha256: Optional[str]
    frozen_truth_label: Optional[str]
    accuracy_status: str
    accuracy_match: Optional[bool]
    gate: str
    public_action_applied: bool
    production_enable_allowed: bool
    receipt_sha256: str
    schema_version: str = COMPARISON_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != COMPARISON_SCHEMA:
            raise ValueError("unsupported early-route comparison schema")
        object.__setattr__(
            self,
            "publication_scope_id",
            _require_sha256(self.publication_scope_id, "publication_scope_id"),
        )
        object.__setattr__(self, "pair_id", _require_text(self.pair_id, "pair_id"))
        _require_positive_int(self.input_index, "input_index")
        object.__setattr__(self, "post_id", _require_text(self.post_id, "post_id"))
        for field_name in (
            "route_decision_sha256",
            "authoritative_wal_receipt_sha256",
            "public_projection_before_sha256",
            "public_projection_after_sha256",
            "receipt_sha256",
        ):
            object.__setattr__(self, field_name, _require_sha256(getattr(self, field_name), field_name))
        if self.selected_lane not in {LANE_FULL, LANE_CHEAP_NIL}:
            raise ValueError("comparison selected_lane is invalid")
        if self.authoritative_wal_outcome not in {"PUBLISH", "HOLD", "ERROR_HOLD"}:
            raise ValueError("authoritative WAL outcome is invalid")
        if self.baseline_equivalence_status not in {
            "BASELINE_EQUIVALENT",
            "BASELINE_MISMATCH",
            "NOT_APPLICABLE_FULL_EXPERT",
        }:
            raise ValueError("baseline equivalence status is invalid")
        if _require_bool(self.baseline_equivalence_is_truth, "baseline_equivalence_is_truth"):
            raise ValueError("WAL parity must never be labeled as truth")
        if self.public_projection_match is not None:
            _require_bool(self.public_projection_match, "public_projection_match")
        if self.public_noninterference_status not in {"GO", "VIOLATION"}:
            raise ValueError("public noninterference status is invalid")
        expected_noninterference = (
            "GO"
            if self.public_projection_before_sha256 == self.public_projection_after_sha256
            else "VIOLATION"
        )
        if self.public_noninterference_status != expected_noninterference:
            raise ValueError("public noninterference status does not match bound fingerprints")
        if self.frozen_truth_status not in {
            FROZEN_TRUTH_NOT_AVAILABLE,
            FROZEN_TRUTH_VERIFIED,
        }:
            raise ValueError("frozen truth status is invalid")
        object.__setattr__(
            self,
            "frozen_truth_receipt_sha256",
            (
                _require_sha256(self.frozen_truth_receipt_sha256, "frozen_truth_receipt_sha256")
                if self.frozen_truth_receipt_sha256 is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "frozen_truth_label",
            _require_optional_text(self.frozen_truth_label, "frozen_truth_label"),
        )
        if self.frozen_truth_status == FROZEN_TRUTH_VERIFIED:
            if self.frozen_truth_receipt_sha256 is None or self.frozen_truth_label is None:
                raise ValueError("verified frozen truth requires a receipt and label")
        elif self.frozen_truth_receipt_sha256 is not None or self.frozen_truth_label is not None:
            raise ValueError("unavailable frozen truth must not carry a receipt or label")
        if self.accuracy_status not in {
            ACCURACY_NOT_ESTIMABLE,
            "MATCH_FROZEN_ACTUAL",
            "MISMATCH_FROZEN_ACTUAL",
            "NOT_APPLICABLE_FULL_EXPERT",
        }:
            raise ValueError("accuracy status is invalid")
        if self.accuracy_match is not None:
            _require_bool(self.accuracy_match, "accuracy_match")
        if self.frozen_truth_status == FROZEN_TRUTH_NOT_AVAILABLE:
            if self.accuracy_status != ACCURACY_NOT_ESTIMABLE or self.accuracy_match is not None:
                raise ValueError("missing P3 truth must keep accuracy NOT_ESTIMABLE")
            if self.gate.startswith("GO"):
                raise ValueError("missing P3 truth can never produce a GO gate")
        elif self.selected_lane == LANE_FULL:
            if self.accuracy_status != "NOT_APPLICABLE_FULL_EXPERT" or self.accuracy_match is not None:
                raise ValueError("full-expert comparison cannot claim cheap-lane accuracy")
        elif self.accuracy_match is True and self.accuracy_status != "MATCH_FROZEN_ACTUAL":
            raise ValueError("frozen-actual accuracy match/status mismatch")
        elif self.accuracy_match is False and self.accuracy_status != "MISMATCH_FROZEN_ACTUAL":
            raise ValueError("frozen-actual accuracy match/status mismatch")

        if self.selected_lane == LANE_FULL:
            if (
                self.baseline_equivalence_status != "NOT_APPLICABLE_FULL_EXPERT"
                or self.public_projection_match is not None
            ):
                raise ValueError("full-expert comparison cannot claim cheap baseline equivalence")
        else:
            if self.public_projection_match is None:
                raise ValueError("cheap comparison requires a public projection comparison")
            expected_baseline = (
                "BASELINE_EQUIVALENT"
                if self.public_projection_match and self.authoritative_wal_outcome == "HOLD"
                else "BASELINE_MISMATCH"
            )
            if self.baseline_equivalence_status != expected_baseline:
                raise ValueError("baseline equivalence status does not match WAL projection parity")

        if self.selected_lane != LANE_CHEAP_NIL:
            expected_gate = "NO_GO_FULL_EXPERT_REQUIRED"
        elif self.public_noninterference_status != "GO":
            expected_gate = "NO_GO_PUBLIC_INTERFERENCE"
        elif self.baseline_equivalence_status != "BASELINE_EQUIVALENT":
            expected_gate = "NO_GO_BASELINE_MISMATCH"
        elif self.accuracy_status == ACCURACY_NOT_ESTIMABLE:
            expected_gate = "NO_GO_ACCURACY_NOT_ESTIMABLE"
        elif self.accuracy_match is not True:
            expected_gate = "NO_GO_FROZEN_ACTUAL_MISMATCH"
        else:
            expected_gate = "GO_MEASUREMENT_COMPARISON_ONLY"
        if self.gate != expected_gate:
            raise ValueError("comparison gate does not match bound evidence statuses")
        if _require_bool(self.public_action_applied, "public_action_applied"):
            raise ValueError("comparison receipt must not apply a public action")
        if _require_bool(self.production_enable_allowed, "production_enable_allowed"):
            raise ValueError("measurement comparison can never enable production")
        if self.receipt_sha256 != canonical_hash(self.payload_without_hash()):
            raise ValueError("early-route comparison fingerprint mismatch")

    def payload_without_hash(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "publication_scope_id": self.publication_scope_id,
            "pair_id": self.pair_id,
            "input_index": self.input_index,
            "post_id": self.post_id,
            "route_decision_sha256": self.route_decision_sha256,
            "selected_lane": self.selected_lane,
            "authoritative_wal_receipt_sha256": self.authoritative_wal_receipt_sha256,
            "authoritative_wal_outcome": self.authoritative_wal_outcome,
            "baseline_equivalence_status": self.baseline_equivalence_status,
            "baseline_equivalence_is_truth": self.baseline_equivalence_is_truth,
            "public_projection_match": self.public_projection_match,
            "public_projection_before_sha256": self.public_projection_before_sha256,
            "public_projection_after_sha256": self.public_projection_after_sha256,
            "public_noninterference_status": self.public_noninterference_status,
            "frozen_truth_status": self.frozen_truth_status,
            "frozen_truth_receipt_sha256": self.frozen_truth_receipt_sha256,
            "frozen_truth_label": self.frozen_truth_label,
            "accuracy_status": self.accuracy_status,
            "accuracy_match": self.accuracy_match,
            "gate": self.gate,
            "public_action_applied": self.public_action_applied,
            "production_enable_allowed": self.production_enable_allowed,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload_without_hash(), "receipt_sha256": self.receipt_sha256}

    @classmethod
    def from_dict(cls, value: Any) -> "EarlyRouteComparisonReceipt":
        if not isinstance(value, Mapping):
            raise ValueError("early-route comparison must be an object")
        _require_exact_keys(value, cls.__dataclass_fields__, "early-route comparison")
        return cls(**dict(value))


def compare_early_route(
    decision: EarlyRouteDecision,
    *,
    authoritative_wal_receipt_sha256: str,
    authoritative_wal_outcome: str,
    authoritative_publish_allowed: bool,
    authoritative_title: Optional[str],
    authoritative_url: Optional[str],
    public_projection_before_sha256: str,
    public_projection_after_sha256: str,
    frozen_truth_status: str = FROZEN_TRUTH_NOT_AVAILABLE,
    frozen_truth_receipt_sha256: Optional[str] = None,
    frozen_truth_label: Optional[str] = None,
) -> EarlyRouteComparisonReceipt:
    """Compare an immutable route with post-route WAL/truth evidence.

    The authoritative WAL is a baseline-equivalence oracle only.  It is not
    semantic truth and none of its values can influence ``decision``.
    """

    if not isinstance(decision, EarlyRouteDecision):
        raise TypeError("decision must be an EarlyRouteDecision")
    wal_receipt_hash = _require_sha256(
        authoritative_wal_receipt_sha256,
        "authoritative_wal_receipt_sha256",
    )
    if authoritative_wal_outcome not in {"PUBLISH", "HOLD", "ERROR_HOLD"}:
        raise ValueError("authoritative WAL outcome is invalid")
    publish_allowed = _require_bool(
        authoritative_publish_allowed,
        "authoritative_publish_allowed",
    )
    wal_title = _require_optional_text(authoritative_title, "authoritative_title")
    wal_url = _require_optional_text(authoritative_url, "authoritative_url")
    if (authoritative_wal_outcome == "PUBLISH") != publish_allowed:
        raise ValueError("authoritative WAL outcome/publish flag mismatch")
    if not publish_allowed and (wal_title is not None or wal_url is not None):
        raise ValueError("non-publish WAL projection must keep title and URL null")
    if publish_allowed and wal_title is None:
        raise ValueError("publish WAL projection requires a title")
    before_hash = _require_sha256(
        public_projection_before_sha256,
        "public_projection_before_sha256",
    )
    after_hash = _require_sha256(
        public_projection_after_sha256,
        "public_projection_after_sha256",
    )
    noninterference = "GO" if before_hash == after_hash else "VIOLATION"

    if decision.selected_lane == LANE_CHEAP_NIL:
        proposal = decision.cheap_proposal
        if proposal is None:
            raise ValueError("cheap decision is missing its proposal")
        projection_match = bool(
            authoritative_wal_outcome == "HOLD"
            and publish_allowed is proposal.publish_allowed
            and wal_title is proposal.official_title
            and wal_url is proposal.official_url
        )
        baseline_status = (
            "BASELINE_EQUIVALENT" if projection_match else "BASELINE_MISMATCH"
        )
    else:
        projection_match = None
        baseline_status = "NOT_APPLICABLE_FULL_EXPERT"

    if frozen_truth_status == FROZEN_TRUTH_NOT_AVAILABLE:
        if frozen_truth_receipt_sha256 is not None or frozen_truth_label is not None:
            raise ValueError("unavailable frozen truth must not carry evidence")
        accuracy_status = ACCURACY_NOT_ESTIMABLE
        accuracy_match = None
    elif frozen_truth_status == FROZEN_TRUTH_VERIFIED:
        if frozen_truth_receipt_sha256 is None or frozen_truth_label is None:
            raise ValueError("verified frozen truth requires a receipt and label")
        _require_sha256(frozen_truth_receipt_sha256, "frozen_truth_receipt_sha256")
        truth_label = _require_text(frozen_truth_label, "frozen_truth_label")
        if decision.selected_lane == LANE_CHEAP_NIL:
            accuracy_match = truth_label == NIL_LABEL
            accuracy_status = (
                "MATCH_FROZEN_ACTUAL" if accuracy_match else "MISMATCH_FROZEN_ACTUAL"
            )
        else:
            accuracy_match = None
            accuracy_status = "NOT_APPLICABLE_FULL_EXPERT"
    else:
        raise ValueError("unsupported frozen truth status")

    if decision.selected_lane != LANE_CHEAP_NIL:
        gate = "NO_GO_FULL_EXPERT_REQUIRED"
    elif noninterference != "GO":
        gate = "NO_GO_PUBLIC_INTERFERENCE"
    elif baseline_status != "BASELINE_EQUIVALENT":
        gate = "NO_GO_BASELINE_MISMATCH"
    elif accuracy_status == ACCURACY_NOT_ESTIMABLE:
        gate = "NO_GO_ACCURACY_NOT_ESTIMABLE"
    elif accuracy_match is not True:
        gate = "NO_GO_FROZEN_ACTUAL_MISMATCH"
    else:
        gate = "GO_MEASUREMENT_COMPARISON_ONLY"

    payload = {
        "schema_version": COMPARISON_SCHEMA,
        "publication_scope_id": decision.publication_scope_id,
        "pair_id": decision.pair_id,
        "input_index": decision.input_index,
        "post_id": decision.post_id,
        "route_decision_sha256": decision.decision_sha256,
        "selected_lane": decision.selected_lane,
        "authoritative_wal_receipt_sha256": wal_receipt_hash,
        "authoritative_wal_outcome": authoritative_wal_outcome,
        "baseline_equivalence_status": baseline_status,
        "baseline_equivalence_is_truth": False,
        "public_projection_match": projection_match,
        "public_projection_before_sha256": before_hash,
        "public_projection_after_sha256": after_hash,
        "public_noninterference_status": noninterference,
        "frozen_truth_status": frozen_truth_status,
        "frozen_truth_receipt_sha256": frozen_truth_receipt_sha256,
        "frozen_truth_label": frozen_truth_label,
        "accuracy_status": accuracy_status,
        "accuracy_match": accuracy_match,
        "gate": gate,
        "public_action_applied": False,
        "production_enable_allowed": False,
    }
    return EarlyRouteComparisonReceipt(
        **payload,
        receipt_sha256=canonical_hash(payload),
    )


__all__ = [
    "ACCURACY_NOT_ESTIMABLE",
    "ACTION_ASSERT_NIL",
    "ARM_AFTER",
    "CHEAP_NIL_SCHEMA",
    "COMPARISON_SCHEMA",
    "DECISION_SCHEMA",
    "FROZEN_TRUTH_NOT_AVAILABLE",
    "FROZEN_TRUTH_VERIFIED",
    "LANE_CHEAP_NIL",
    "LANE_FULL",
    "NIL_LABEL",
    "POLICY_SCHEMA",
    "SOURCE_VIEW_SCHEMA",
    "CheapNilProposal",
    "EarlyRouteComparisonReceipt",
    "EarlyRouteDecision",
    "EarlyRoutePolicyV1",
    "EarlyRouteSourceView",
    "canonical_hash",
    "compare_early_route",
    "decide_early_route",
]
