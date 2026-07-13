"""후보 보존 목록의 로컬 완전성 상태를 기록하는 불변 계약.

이 계약은 serializer가 실제로 관측한 후보 보존 source만 다룬다. 상류 후보
생성기가 모든 후보를 열거했다는 증거는 아니므로 v1은 ``COMPLETE``를 만들지
않는다. 로컬 고유 source가 보존 cap을 넘으면 ``TRUNCATED``, 그 외에는
``UNKNOWN``이다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

from .promotion_gate import _canonical_url, _title_key


CANDIDATE_GENERATION_VERSION = "candidate_generation_v1"
CANDIDATE_GENERATION_SCOPE = "serializer_preservation_inventory"
CANDIDATE_GENERATION_COUNT_BASIS = "normalized_title_url_role_unique"
CANDIDATE_GENERATION_UPSTREAM_COMPLETENESS = "UNKNOWN"
TITLE_CANDIDATE_GENERATION_VERSION = "title_candidate_generation_v1"
TITLE_CANDIDATE_GENERATION_SCOPE = "title_candidate_ranked_inventory"
TITLE_CANDIDATE_GENERATION_COUNT_BASIS = "normalized_title_unique_after_policy_prune"
CANDIDATE_STAGE_RECEIPT_VERSION = "candidate_stage_receipt_v1"
CANDIDATE_STAGE_RECEIPT_SCOPE = "expert_stage_candidate_inventory"
CANDIDATE_STAGE_RECEIPT_COUNT_BASIS = (
    "normalized_title_unique_before_stage_row_cap"
)
CANDIDATE_PRODUCER_PLAN_VERSION = "candidate_producer_plan_v1"
CANDIDATE_PRODUCER_PLAN_SCOPE = "bounded_candidate_producer_plan"
CANDIDATE_PRODUCER_RECEIPT_VERSION = "candidate_producer_receipt_v1"
CANDIDATE_PRODUCER_RECEIPT_SCOPE = "bounded_candidate_producer_operation"
CANDIDATE_GENERATION_PROOF_VERSION = "candidate_generation_proof_v1"
CANDIDATE_GENERATION_PROOF_SCOPE = "bounded_candidate_generation_proof"
CANDIDATE_PRODUCER_KINDS = frozenset({"search", "fetch"})
CANDIDATE_REQUIRED_PRODUCERS = ("fetch", "search")

# 이 목록은 공개 CandidateSet이 아니라 전문가 내부 상태를 실제로 자르는 경계만
# 고정한다. prompt 요약용 slice나 원본 LLM 응답 검사용 slice는 포함하지 않는다.
CANDIDATE_STAGE_RULES = {
    ("gatekeeper", "comment_title_candidates"): 8,
    ("decoder", "new_suspected_titles"): 5,
    ("verifier", "ranked_update"): 5,
    ("verifier", "comment_boost"): 5,
    ("arbiter", "critic_filter"): 5,
    ("arbiter", "candidate_merge"): 5,
    ("arbiter", "llm_candidate_merge"): 5,
}

_CONTRACT_RULES = {
    CANDIDATE_GENERATION_VERSION: {
        "scope": CANDIDATE_GENERATION_SCOPE,
        "count_basis": CANDIDATE_GENERATION_COUNT_BASIS,
        "truncated_reason": "serializer_preservation_inventory_truncated",
    },
    TITLE_CANDIDATE_GENERATION_VERSION: {
        "scope": TITLE_CANDIDATE_GENERATION_SCOPE,
        "count_basis": TITLE_CANDIDATE_GENERATION_COUNT_BASIS,
        "truncated_reason": "title_candidate_ranked_inventory_truncated",
    },
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LEDGER_FIELDS = {
    "schema_version",
    "scope",
    "status",
    "cap",
    "unique_valid_source_count",
    "emitted_source_count",
    "count_basis",
    "upstream_completeness",
    "source_key_fingerprint",
    "observed_sources_fingerprint",
    "retained_sources_fingerprint",
    "reason_codes",
    "metadata_fingerprint",
}

_STAGE_RECEIPT_FIELDS = {
    "schema_version",
    "scope",
    "producer",
    "stage",
    "occurrence",
    "status",
    "cap",
    "observed_source_count",
    "retained_source_count",
    "unique_valid_source_count",
    "emitted_source_count",
    "count_basis",
    "upstream_completeness",
    "source_key_fingerprint",
    "observed_sources_fingerprint",
    "retained_sources_fingerprint",
    "reason_codes",
    "metadata_fingerprint",
}

_PRODUCER_PLAN_FIELDS = {
    "schema_version",
    "scope",
    "producer",
    "occurrence",
    "plan_fingerprint",
    "planned_operation_count",
    "planned_operation_fingerprints",
    "enumeration_finished",
    "reason_codes",
    "metadata_fingerprint",
}

_PRODUCER_RECEIPT_FIELDS = {
    "schema_version",
    "scope",
    "producer",
    "plan_fingerprint",
    "operation_id",
    "occurrence",
    "status",
    "input_fingerprint",
    "attempted_count",
    "raw_count",
    "accepted_count",
    "enumeration_finished",
    "from_cache",
    "degraded",
    "possible_throttle",
    "error_status",
    "output_fingerprint",
    "reason_codes",
    "metadata_fingerprint",
}

_GENERATION_PROOF_FIELDS = {
    "schema_version",
    "scope",
    "status",
    "upstream_completeness",
    "required_producers",
    "observed_producers",
    "plan_count",
    "planned_operation_count",
    "receipt_count",
    "complete_receipt_count",
    "unknown_receipt_count",
    "truncated_receipt_count",
    "unfinished_plan_count",
    "missing_receipt_count",
    "extra_receipt_count",
    "local_snapshot_count",
    "local_truncated_count",
    "plan_set_fingerprint",
    "receipt_set_fingerprint",
    "reason_codes",
    "metadata_fingerprint",
}


def _canonical_payload(value: Any) -> Any:
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


def _require_sha256(value: Any, field_name: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"{field_name} must be a sha256 hex digest")
    return text


def _strict_nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative int")
    return value


def _strict_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive int")
    return value


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a bool")
    return value


def _strict_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple")
    return value


def _source_payload(value: Any) -> Optional[dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    payload = {
        str(key): item
        for key, item in value.items()
        if item is not None
    }
    title = str(
        payload.get("official_title")
        or payload.get("title")
        or payload.get("name")
        or ""
    ).strip()
    if not title:
        return None
    return payload


def _source_key(
    value: Mapping[str, Any],
    *,
    schema_version: str,
) -> tuple[str, str, str]:
    title = str(
        value.get("official_title")
        or value.get("title")
        or value.get("name")
        or ""
    ).strip()
    url = str(value.get("heretic_url") or value.get("url") or "").strip()
    role = str(value.get("preservation_role") or "").strip().casefold()
    title_key = _title_key(title)
    if schema_version == TITLE_CANDIDATE_GENERATION_VERSION:
        # `_build_title_candidates` has already merged rows by normalized title
        # before ranking.  Keep the frozen contract on that exact count basis:
        # alternate URLs/roles for the same normalized title are observations,
        # not additional ranked-title events.
        return (title_key, "", "")
    return (title_key, _canonical_url(url), role)


def _unique_sources(
    values: Iterable[Any],
    *,
    schema_version: str,
) -> tuple[tuple[dict[str, Any], ...], tuple[tuple[str, str, str], ...]]:
    sources: list[dict[str, Any]] = []
    keys: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for value in values:
        payload = _source_payload(value)
        if payload is None:
            continue
        key = _source_key(payload, schema_version=schema_version)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        sources.append(payload)
        keys.append(key)
    return tuple(sources), tuple(keys)


@dataclass(frozen=True)
class CandidateGenerationSnapshot:
    status: str
    cap: int
    unique_valid_source_count: int
    emitted_source_count: int
    source_key_fingerprint: str
    observed_sources_fingerprint: str
    retained_sources_fingerprint: str
    reason_codes: Tuple[str, ...]
    metadata_fingerprint: str
    retained_sources: Optional[Tuple[dict[str, Any], ...]] = field(
        default=None,
        repr=False,
        compare=False,
    )
    schema_version: str = CANDIDATE_GENERATION_VERSION
    scope: str = CANDIDATE_GENERATION_SCOPE
    count_basis: str = CANDIDATE_GENERATION_COUNT_BASIS
    upstream_completeness: str = CANDIDATE_GENERATION_UPSTREAM_COMPLETENESS

    def __post_init__(self) -> None:
        rules = _CONTRACT_RULES.get(self.schema_version)
        if rules is None:
            raise ValueError("unsupported candidate generation schema_version")
        if self.scope != rules["scope"]:
            raise ValueError("unsupported candidate generation scope")
        if self.count_basis != rules["count_basis"]:
            raise ValueError("unsupported candidate generation count_basis")
        if self.upstream_completeness != CANDIDATE_GENERATION_UPSTREAM_COMPLETENESS:
            raise ValueError("upstream_completeness must remain UNKNOWN in v1")
        if self.status not in {"UNKNOWN", "TRUNCATED"}:
            raise ValueError("status must be UNKNOWN or TRUNCATED in candidate_generation_v1")
        _strict_positive_int(self.cap, "cap")
        _strict_nonnegative_int(
            self.unique_valid_source_count,
            "unique_valid_source_count",
        )
        _strict_nonnegative_int(self.emitted_source_count, "emitted_source_count")
        expected_emitted = min(self.unique_valid_source_count, self.cap)
        if self.emitted_source_count != expected_emitted:
            raise ValueError("emitted_source_count does not match count/cap")
        expected_status = (
            "TRUNCATED"
            if self.unique_valid_source_count > self.cap
            else "UNKNOWN"
        )
        if self.status != expected_status:
            raise ValueError("candidate generation status does not match count/cap")
        expected_reasons = ["upstream_completeness_unknown"]
        if self.status == "TRUNCATED":
            expected_reasons.append(str(rules["truncated_reason"]))
        normalized_reasons = tuple(sorted({str(item or "").strip() for item in self.reason_codes if str(item or "").strip()}))
        object.__setattr__(self, "reason_codes", normalized_reasons)
        if normalized_reasons != tuple(sorted(expected_reasons)):
            raise ValueError("candidate generation reason_codes mismatch")
        for field_name in (
            "source_key_fingerprint",
            "observed_sources_fingerprint",
            "retained_sources_fingerprint",
            "metadata_fingerprint",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        if self.retained_sources is not None:
            normalized_sources, _keys = _unique_sources(
                self.retained_sources,
                schema_version=self.schema_version,
            )
            object.__setattr__(self, "retained_sources", normalized_sources)
            if len(normalized_sources) != self.emitted_source_count:
                raise ValueError("retained source count mismatch")
            if _canonical_hash(list(normalized_sources)) != self.retained_sources_fingerprint:
                raise ValueError("retained sources fingerprint mismatch")
            if self.status == "UNKNOWN" and self.observed_sources_fingerprint != self.retained_sources_fingerprint:
                raise ValueError("untruncated observed/retained fingerprint mismatch")
        if _canonical_hash(self.payload_without_metadata_fingerprint()) != self.metadata_fingerprint:
            raise ValueError("metadata_fingerprint mismatch")

    def payload_without_metadata_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "status": self.status,
            "cap": self.cap,
            "unique_valid_source_count": self.unique_valid_source_count,
            "emitted_source_count": self.emitted_source_count,
            "count_basis": self.count_basis,
            "upstream_completeness": self.upstream_completeness,
            "source_key_fingerprint": self.source_key_fingerprint,
            "observed_sources_fingerprint": self.observed_sources_fingerprint,
            "retained_sources_fingerprint": self.retained_sources_fingerprint,
            "reason_codes": list(self.reason_codes),
        }

    def to_ledger_dict(self) -> dict[str, Any]:
        return {
            **self.payload_without_metadata_fingerprint(),
            "metadata_fingerprint": self.metadata_fingerprint,
        }


def _build_generation_snapshot(
    observed_sources: Iterable[Any],
    *,
    cap: int,
    schema_version: str,
) -> CandidateGenerationSnapshot:
    rules = _CONTRACT_RULES.get(schema_version)
    if rules is None:
        raise ValueError("unsupported candidate generation schema_version")
    normalized_cap = _strict_positive_int(cap, "cap")
    sources, keys = _unique_sources(
        tuple(observed_sources),
        schema_version=schema_version,
    )
    retained = sources[:normalized_cap]
    status = "TRUNCATED" if len(sources) > normalized_cap else "UNKNOWN"
    reasons = ["upstream_completeness_unknown"]
    if status == "TRUNCATED":
        reasons.append(str(rules["truncated_reason"]))
    payload = {
        "schema_version": schema_version,
        "scope": rules["scope"],
        "status": status,
        "cap": normalized_cap,
        "unique_valid_source_count": len(sources),
        "emitted_source_count": len(retained),
        "count_basis": rules["count_basis"],
        "upstream_completeness": CANDIDATE_GENERATION_UPSTREAM_COMPLETENESS,
        "source_key_fingerprint": _canonical_hash(sorted([list(key) for key in keys])),
        "observed_sources_fingerprint": _canonical_hash(list(sources)),
        "retained_sources_fingerprint": _canonical_hash(list(retained)),
        "reason_codes": sorted(reasons),
    }
    return CandidateGenerationSnapshot(
        status=status,
        cap=normalized_cap,
        unique_valid_source_count=len(sources),
        emitted_source_count=len(retained),
        source_key_fingerprint=payload["source_key_fingerprint"],
        observed_sources_fingerprint=payload["observed_sources_fingerprint"],
        retained_sources_fingerprint=payload["retained_sources_fingerprint"],
        reason_codes=tuple(payload["reason_codes"]),
        metadata_fingerprint=_canonical_hash(payload),
        retained_sources=retained,
        schema_version=schema_version,
        scope=str(rules["scope"]),
        count_basis=str(rules["count_basis"]),
    )


def build_candidate_generation_snapshot(
    observed_sources: Iterable[Any],
    *,
    cap: int = 24,
) -> CandidateGenerationSnapshot:
    """Build the serializer-local snapshot without claiming completeness."""

    return _build_generation_snapshot(
        observed_sources,
        cap=cap,
        schema_version=CANDIDATE_GENERATION_VERSION,
    )


def build_title_candidate_generation_snapshot(
    observed_sources: Iterable[Any],
    *,
    cap: int = 6,
) -> CandidateGenerationSnapshot:
    """Build the main ranked-title stage snapshot without claiming completeness."""

    return _build_generation_snapshot(
        observed_sources,
        cap=cap,
        schema_version=TITLE_CANDIDATE_GENERATION_VERSION,
    )


def candidate_generation_snapshot_from_dict(
    value: Any,
    *,
    retained_sources: Optional[Iterable[Any]] = None,
) -> CandidateGenerationSnapshot:
    if not isinstance(value, Mapping):
        raise ValueError("candidate generation snapshot must be an object")
    fields = {str(key) for key in value.keys()}
    if fields != _LEDGER_FIELDS:
        missing = sorted(_LEDGER_FIELDS - fields)
        extra = sorted(fields - _LEDGER_FIELDS)
        raise ValueError(f"candidate generation fields mismatch missing={missing} extra={extra}")
    status = str(value.get("status") or "").strip().upper()
    if status not in {"UNKNOWN", "TRUNCATED"}:
        raise ValueError("status must be UNKNOWN or TRUNCATED in candidate_generation_v1")
    schema_version = str(value.get("schema_version") or "")
    if schema_version not in _CONTRACT_RULES:
        raise ValueError("unsupported candidate generation schema_version")
    normalized_retained: Optional[Tuple[dict[str, Any], ...]] = None
    if retained_sources is not None:
        normalized_retained, _keys = _unique_sources(
            tuple(retained_sources),
            schema_version=schema_version,
        )
    return CandidateGenerationSnapshot(
        status=status,
        cap=_strict_positive_int(value.get("cap"), "cap"),
        unique_valid_source_count=_strict_nonnegative_int(
            value.get("unique_valid_source_count"),
            "unique_valid_source_count",
        ),
        emitted_source_count=_strict_nonnegative_int(
            value.get("emitted_source_count"),
            "emitted_source_count",
        ),
        source_key_fingerprint=_require_sha256(
            value.get("source_key_fingerprint"),
            "source_key_fingerprint",
        ),
        observed_sources_fingerprint=_require_sha256(
            value.get("observed_sources_fingerprint"),
            "observed_sources_fingerprint",
        ),
        retained_sources_fingerprint=_require_sha256(
            value.get("retained_sources_fingerprint"),
            "retained_sources_fingerprint",
        ),
        reason_codes=tuple(
            str(item or "").strip()
            for item in _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        metadata_fingerprint=_require_sha256(
            value.get("metadata_fingerprint"),
            "metadata_fingerprint",
        ),
        retained_sources=normalized_retained,
        schema_version=schema_version,
        scope=str(value.get("scope") or ""),
        count_basis=str(value.get("count_basis") or ""),
        upstream_completeness=str(value.get("upstream_completeness") or ""),
    )


def _stage_title_key(value: Any) -> str:
    if isinstance(value, str):
        title = value
    elif isinstance(value, Mapping):
        title = str(
            value.get("title")
            or value.get("official_title")
            or value.get("official_novel_title")
            or value.get("name")
            or ""
        )
    else:
        return ""
    return _title_key(str(title or "").strip())


@dataclass(frozen=True)
class CandidateStageReceipt:
    """전문가 내부 cap 직전 후보 목록을 원문 비노출 hash로 증명한다.

    이 영수증은 진단 전용이다. CandidateSet의 완전성, 공개 제목/URL,
    promotion 판정 또는 확률값을 직접 변경하지 않는다.
    """

    producer: str
    stage: str
    occurrence: int
    status: str
    cap: int
    observed_source_count: int
    retained_source_count: int
    unique_valid_source_count: int
    emitted_source_count: int
    source_key_fingerprint: str
    observed_sources_fingerprint: str
    retained_sources_fingerprint: str
    reason_codes: Tuple[str, ...]
    metadata_fingerprint: str
    schema_version: str = CANDIDATE_STAGE_RECEIPT_VERSION
    scope: str = CANDIDATE_STAGE_RECEIPT_SCOPE
    count_basis: str = CANDIDATE_STAGE_RECEIPT_COUNT_BASIS
    upstream_completeness: str = CANDIDATE_GENERATION_UPSTREAM_COMPLETENESS

    def __post_init__(self) -> None:
        if self.schema_version != CANDIDATE_STAGE_RECEIPT_VERSION:
            raise ValueError("unsupported candidate stage receipt schema_version")
        if self.scope != CANDIDATE_STAGE_RECEIPT_SCOPE:
            raise ValueError("unsupported candidate stage receipt scope")
        if self.count_basis != CANDIDATE_STAGE_RECEIPT_COUNT_BASIS:
            raise ValueError("unsupported candidate stage receipt count_basis")
        if self.upstream_completeness != CANDIDATE_GENERATION_UPSTREAM_COMPLETENESS:
            raise ValueError("candidate stage upstream_completeness must remain UNKNOWN")
        expected_cap = CANDIDATE_STAGE_RULES.get((self.producer, self.stage))
        if expected_cap is None:
            raise ValueError("unsupported candidate stage receipt producer/stage")
        _strict_positive_int(self.occurrence, "occurrence")
        _strict_positive_int(self.cap, "cap")
        if self.cap != expected_cap:
            raise ValueError("candidate stage receipt cap does not match frozen rule")
        for field_name, value in (
            ("observed_source_count", self.observed_source_count),
            ("retained_source_count", self.retained_source_count),
            ("unique_valid_source_count", self.unique_valid_source_count),
            ("emitted_source_count", self.emitted_source_count),
        ):
            _strict_nonnegative_int(value, field_name)
        if self.retained_source_count != min(self.observed_source_count, self.cap):
            raise ValueError("retained_source_count does not match observed count/cap")
        if self.unique_valid_source_count > self.observed_source_count:
            raise ValueError("unique_valid_source_count exceeds observed_source_count")
        if self.emitted_source_count > self.retained_source_count:
            raise ValueError("emitted_source_count exceeds retained_source_count")
        if self.emitted_source_count > self.unique_valid_source_count:
            raise ValueError("emitted_source_count exceeds unique_valid_source_count")
        expected_status = (
            "TRUNCATED"
            if self.unique_valid_source_count > self.emitted_source_count
            else "UNKNOWN"
        )
        if self.status != expected_status:
            raise ValueError("candidate stage receipt status does not match unique loss")
        expected_reasons = ["upstream_completeness_unknown"]
        if expected_status == "TRUNCATED":
            expected_reasons.append("stage_local_candidate_inventory_truncated")
        normalized_reasons = tuple(
            sorted(
                {
                    str(item or "").strip()
                    for item in self.reason_codes
                    if str(item or "").strip()
                }
            )
        )
        if normalized_reasons != tuple(sorted(expected_reasons)):
            raise ValueError("candidate stage receipt reason_codes mismatch")
        object.__setattr__(self, "reason_codes", normalized_reasons)
        for field_name, value in (
            ("source_key_fingerprint", self.source_key_fingerprint),
            ("observed_sources_fingerprint", self.observed_sources_fingerprint),
            ("retained_sources_fingerprint", self.retained_sources_fingerprint),
            ("metadata_fingerprint", self.metadata_fingerprint),
        ):
            _require_sha256(value, field_name)
        if self.metadata_fingerprint != _canonical_hash(
            self.payload_without_metadata_fingerprint()
        ):
            raise ValueError("candidate stage receipt metadata_fingerprint mismatch")

    def payload_without_metadata_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "producer": self.producer,
            "stage": self.stage,
            "occurrence": self.occurrence,
            "status": self.status,
            "cap": self.cap,
            "observed_source_count": self.observed_source_count,
            "retained_source_count": self.retained_source_count,
            "unique_valid_source_count": self.unique_valid_source_count,
            "emitted_source_count": self.emitted_source_count,
            "count_basis": self.count_basis,
            "upstream_completeness": self.upstream_completeness,
            "source_key_fingerprint": self.source_key_fingerprint,
            "observed_sources_fingerprint": self.observed_sources_fingerprint,
            "retained_sources_fingerprint": self.retained_sources_fingerprint,
            "reason_codes": list(self.reason_codes),
        }

    def to_ledger_dict(self) -> dict[str, Any]:
        return {
            **self.payload_without_metadata_fingerprint(),
            "metadata_fingerprint": self.metadata_fingerprint,
        }


def build_candidate_stage_receipt(
    observed_sources: Iterable[Any],
    *,
    producer: str,
    stage: str,
    occurrence: int = 1,
) -> CandidateStageReceipt:
    normalized_producer = str(producer or "").strip().casefold()
    normalized_stage = str(stage or "").strip().casefold()
    cap = CANDIDATE_STAGE_RULES.get((normalized_producer, normalized_stage))
    if cap is None:
        raise ValueError("unsupported candidate stage receipt producer/stage")
    _strict_positive_int(occurrence, "occurrence")
    observed_keys = tuple(
        key for key in (_stage_title_key(value) for value in observed_sources) if key
    )
    retained_keys = observed_keys[:cap]
    unique_observed = tuple(dict.fromkeys(observed_keys))
    unique_retained = tuple(dict.fromkeys(retained_keys))
    status = "TRUNCATED" if len(unique_observed) > len(unique_retained) else "UNKNOWN"
    reasons = ["upstream_completeness_unknown"]
    if status == "TRUNCATED":
        reasons.append("stage_local_candidate_inventory_truncated")
    payload = {
        "schema_version": CANDIDATE_STAGE_RECEIPT_VERSION,
        "scope": CANDIDATE_STAGE_RECEIPT_SCOPE,
        "producer": normalized_producer,
        "stage": normalized_stage,
        "occurrence": occurrence,
        "status": status,
        "cap": cap,
        "observed_source_count": len(observed_keys),
        "retained_source_count": len(retained_keys),
        "unique_valid_source_count": len(unique_observed),
        "emitted_source_count": len(unique_retained),
        "count_basis": CANDIDATE_STAGE_RECEIPT_COUNT_BASIS,
        "upstream_completeness": CANDIDATE_GENERATION_UPSTREAM_COMPLETENESS,
        "source_key_fingerprint": _canonical_hash(sorted(unique_observed)),
        "observed_sources_fingerprint": _canonical_hash(list(observed_keys)),
        "retained_sources_fingerprint": _canonical_hash(list(retained_keys)),
        "reason_codes": sorted(reasons),
    }
    return CandidateStageReceipt(
        producer=normalized_producer,
        stage=normalized_stage,
        occurrence=occurrence,
        status=status,
        cap=cap,
        observed_source_count=len(observed_keys),
        retained_source_count=len(retained_keys),
        unique_valid_source_count=len(unique_observed),
        emitted_source_count=len(unique_retained),
        source_key_fingerprint=payload["source_key_fingerprint"],
        observed_sources_fingerprint=payload["observed_sources_fingerprint"],
        retained_sources_fingerprint=payload["retained_sources_fingerprint"],
        reason_codes=tuple(payload["reason_codes"]),
        metadata_fingerprint=_canonical_hash(payload),
    )


def candidate_stage_receipt_from_dict(value: Any) -> CandidateStageReceipt:
    if not isinstance(value, Mapping):
        raise ValueError("candidate stage receipt must be an object")
    fields = {str(key) for key in value.keys()}
    if fields != _STAGE_RECEIPT_FIELDS:
        missing = sorted(_STAGE_RECEIPT_FIELDS - fields)
        extra = sorted(fields - _STAGE_RECEIPT_FIELDS)
        raise ValueError(
            f"candidate stage receipt fields mismatch missing={missing} extra={extra}"
        )
    return CandidateStageReceipt(
        producer=str(value.get("producer") or "").strip().casefold(),
        stage=str(value.get("stage") or "").strip().casefold(),
        occurrence=_strict_positive_int(value.get("occurrence"), "occurrence"),
        status=str(value.get("status") or "").strip().upper(),
        cap=_strict_positive_int(value.get("cap"), "cap"),
        observed_source_count=_strict_nonnegative_int(
            value.get("observed_source_count"), "observed_source_count"
        ),
        retained_source_count=_strict_nonnegative_int(
            value.get("retained_source_count"), "retained_source_count"
        ),
        unique_valid_source_count=_strict_nonnegative_int(
            value.get("unique_valid_source_count"), "unique_valid_source_count"
        ),
        emitted_source_count=_strict_nonnegative_int(
            value.get("emitted_source_count"), "emitted_source_count"
        ),
        source_key_fingerprint=_require_sha256(
            value.get("source_key_fingerprint"), "source_key_fingerprint"
        ),
        observed_sources_fingerprint=_require_sha256(
            value.get("observed_sources_fingerprint"),
            "observed_sources_fingerprint",
        ),
        retained_sources_fingerprint=_require_sha256(
            value.get("retained_sources_fingerprint"),
            "retained_sources_fingerprint",
        ),
        reason_codes=tuple(
            str(item or "").strip()
            for item in _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        metadata_fingerprint=_require_sha256(
            value.get("metadata_fingerprint"), "metadata_fingerprint"
        ),
        schema_version=str(value.get("schema_version") or ""),
        scope=str(value.get("scope") or ""),
        count_basis=str(value.get("count_basis") or ""),
        upstream_completeness=str(value.get("upstream_completeness") or ""),
    )


def candidate_stage_receipts_from_payload(
    value: Any,
) -> Tuple[CandidateStageReceipt, ...]:
    receipts = tuple(
        candidate_stage_receipt_from_dict(item)
        for item in _strict_sequence(value, "candidate_stage_receipts")
    )
    identities = [
        (receipt.producer, receipt.stage, receipt.occurrence)
        for receipt in receipts
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate candidate stage receipt occurrence")
    return receipts


def record_candidate_stage_receipt(
    ctx: Any,
    *,
    producer: str,
    stage: str,
    observed_sources: Iterable[Any],
) -> Optional[CandidateStageReceipt]:
    """Append a private receipt without changing expert outputs or prompts."""

    if ctx is None:
        return None
    existing = getattr(ctx, "_candidate_generation_stage_receipts", None)
    if not isinstance(existing, list):
        existing = []
        setattr(ctx, "_candidate_generation_stage_receipts", existing)
    normalized_producer = str(producer or "").strip().casefold()
    normalized_stage = str(stage or "").strip().casefold()
    validated_existing = candidate_stage_receipts_from_payload(existing)
    prior = [
        item
        for item in validated_existing
        if item.producer == normalized_producer and item.stage == normalized_stage
    ]
    occurrence = max((item.occurrence for item in prior), default=0) + 1
    receipt = build_candidate_stage_receipt(
        tuple(observed_sources),
        producer=normalized_producer,
        stage=normalized_stage,
        occurrence=occurrence,
    )
    existing.append(receipt.to_ledger_dict())
    return receipt


def _normalized_producer(value: Any) -> str:
    producer = str(value or "").strip().casefold()
    if producer not in CANDIDATE_PRODUCER_KINDS:
        raise ValueError("unsupported candidate producer")
    return producer


def candidate_producer_input_fingerprint(
    producer: str,
    operation_input: Any,
    *,
    purpose: str = "",
) -> str:
    """Return a redacted operation fingerprint without serializing raw input."""

    normalized_producer = _normalized_producer(producer)
    normalized_purpose = " ".join(str(purpose or "").split()).strip().casefold()
    if isinstance(operation_input, Mapping):
        normalized_purpose = " ".join(
            str(operation_input.get("purpose") or normalized_purpose or "").split()
        ).strip().casefold()
        if normalized_producer == "search":
            raw_input = operation_input.get("query") or operation_input.get("input") or ""
        else:
            raw_input = operation_input.get("url") or operation_input.get("input") or ""
    else:
        raw_input = operation_input
    if normalized_producer == "search":
        normalized_input = " ".join(str(raw_input or "").split()).strip().casefold()
    else:
        normalized_input = _canonical_url(str(raw_input or "").strip())
    if not normalized_input:
        raise ValueError("candidate producer operation input must not be empty")
    return _canonical_hash(
        {
            "producer": normalized_producer,
            "purpose": normalized_purpose,
            "input": normalized_input,
        }
    )


@dataclass(frozen=True)
class CandidateProducerPlan:
    """Redacted bounded operation plan for one candidate producer."""

    producer: str
    occurrence: int
    plan_fingerprint: str
    planned_operation_count: int
    planned_operation_fingerprints: Tuple[str, ...]
    enumeration_finished: bool
    reason_codes: Tuple[str, ...]
    metadata_fingerprint: str
    schema_version: str = CANDIDATE_PRODUCER_PLAN_VERSION
    scope: str = CANDIDATE_PRODUCER_PLAN_SCOPE

    def __post_init__(self) -> None:
        producer = _normalized_producer(self.producer)
        object.__setattr__(self, "producer", producer)
        if self.schema_version != CANDIDATE_PRODUCER_PLAN_VERSION:
            raise ValueError("unsupported candidate producer plan schema_version")
        if self.scope != CANDIDATE_PRODUCER_PLAN_SCOPE:
            raise ValueError("unsupported candidate producer plan scope")
        _strict_positive_int(self.occurrence, "occurrence")
        _strict_nonnegative_int(
            self.planned_operation_count,
            "planned_operation_count",
        )
        fingerprints = tuple(
            _require_sha256(item, "planned_operation_fingerprint")
            for item in self.planned_operation_fingerprints
        )
        object.__setattr__(self, "planned_operation_fingerprints", fingerprints)
        if len(fingerprints) != self.planned_operation_count:
            raise ValueError("planned operation count/fingerprint mismatch")
        _strict_bool(self.enumeration_finished, "enumeration_finished")
        expected_reasons = [
            "bounded_plan_finished"
            if self.enumeration_finished
            else "bounded_plan_unfinished"
        ]
        if not fingerprints:
            expected_reasons.append("bounded_plan_empty")
        normalized_reasons = tuple(
            sorted(
                {
                    str(item or "").strip()
                    for item in self.reason_codes
                    if str(item or "").strip()
                }
            )
        )
        object.__setattr__(self, "reason_codes", normalized_reasons)
        if normalized_reasons != tuple(sorted(expected_reasons)):
            raise ValueError("candidate producer plan reason_codes mismatch")
        _require_sha256(self.plan_fingerprint, "plan_fingerprint")
        _require_sha256(self.metadata_fingerprint, "metadata_fingerprint")
        expected_plan_fingerprint = _canonical_hash(
            {
                "schema_version": self.schema_version,
                "scope": self.scope,
                "producer": self.producer,
                "occurrence": self.occurrence,
                "planned_operation_fingerprints": list(fingerprints),
            }
        )
        if self.plan_fingerprint != expected_plan_fingerprint:
            raise ValueError("candidate producer plan fingerprint mismatch")
        if self.metadata_fingerprint != _canonical_hash(
            self.payload_without_metadata_fingerprint()
        ):
            raise ValueError("candidate producer plan metadata_fingerprint mismatch")

    def payload_without_metadata_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "producer": self.producer,
            "occurrence": self.occurrence,
            "plan_fingerprint": self.plan_fingerprint,
            "planned_operation_count": self.planned_operation_count,
            "planned_operation_fingerprints": list(
                self.planned_operation_fingerprints
            ),
            "enumeration_finished": self.enumeration_finished,
            "reason_codes": list(self.reason_codes),
        }

    def to_ledger_dict(self) -> dict[str, Any]:
        return {
            **self.payload_without_metadata_fingerprint(),
            "metadata_fingerprint": self.metadata_fingerprint,
        }


def build_candidate_producer_plan(
    operation_inputs: Iterable[Any],
    *,
    producer: str,
    occurrence: int = 1,
    enumeration_finished: bool,
) -> CandidateProducerPlan:
    normalized_producer = _normalized_producer(producer)
    normalized_occurrence = _strict_positive_int(occurrence, "occurrence")
    _strict_bool(enumeration_finished, "enumeration_finished")
    operation_fingerprints = tuple(
        candidate_producer_input_fingerprint(
            normalized_producer,
            item,
            purpose=(
                str(item.get("purpose") or "")
                if isinstance(item, Mapping)
                else ""
            ),
        )
        for item in tuple(operation_inputs)
    )
    plan_fingerprint = _canonical_hash(
        {
            "schema_version": CANDIDATE_PRODUCER_PLAN_VERSION,
            "scope": CANDIDATE_PRODUCER_PLAN_SCOPE,
            "producer": normalized_producer,
            "occurrence": normalized_occurrence,
            "planned_operation_fingerprints": list(operation_fingerprints),
        }
    )
    reasons = [
        "bounded_plan_finished" if enumeration_finished else "bounded_plan_unfinished"
    ]
    if not operation_fingerprints:
        reasons.append("bounded_plan_empty")
    payload = {
        "schema_version": CANDIDATE_PRODUCER_PLAN_VERSION,
        "scope": CANDIDATE_PRODUCER_PLAN_SCOPE,
        "producer": normalized_producer,
        "occurrence": normalized_occurrence,
        "plan_fingerprint": plan_fingerprint,
        "planned_operation_count": len(operation_fingerprints),
        "planned_operation_fingerprints": list(operation_fingerprints),
        "enumeration_finished": enumeration_finished,
        "reason_codes": sorted(reasons),
    }
    return CandidateProducerPlan(
        producer=normalized_producer,
        occurrence=normalized_occurrence,
        plan_fingerprint=plan_fingerprint,
        planned_operation_count=len(operation_fingerprints),
        planned_operation_fingerprints=operation_fingerprints,
        enumeration_finished=enumeration_finished,
        reason_codes=tuple(payload["reason_codes"]),
        metadata_fingerprint=_canonical_hash(payload),
    )


def candidate_producer_plan_from_dict(value: Any) -> CandidateProducerPlan:
    if not isinstance(value, Mapping):
        raise ValueError("candidate producer plan must be an object")
    fields = {str(key) for key in value.keys()}
    if fields != _PRODUCER_PLAN_FIELDS:
        missing = sorted(_PRODUCER_PLAN_FIELDS - fields)
        extra = sorted(fields - _PRODUCER_PLAN_FIELDS)
        raise ValueError(
            f"candidate producer plan fields mismatch missing={missing} extra={extra}"
        )
    return CandidateProducerPlan(
        producer=str(value.get("producer") or ""),
        occurrence=_strict_positive_int(value.get("occurrence"), "occurrence"),
        plan_fingerprint=_require_sha256(
            value.get("plan_fingerprint"), "plan_fingerprint"
        ),
        planned_operation_count=_strict_nonnegative_int(
            value.get("planned_operation_count"),
            "planned_operation_count",
        ),
        planned_operation_fingerprints=tuple(
            _require_sha256(item, "planned_operation_fingerprint")
            for item in _strict_sequence(
                value.get("planned_operation_fingerprints"),
                "planned_operation_fingerprints",
            )
        ),
        enumeration_finished=_strict_bool(
            value.get("enumeration_finished"), "enumeration_finished"
        ),
        reason_codes=tuple(
            str(item or "").strip()
            for item in _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        metadata_fingerprint=_require_sha256(
            value.get("metadata_fingerprint"), "metadata_fingerprint"
        ),
        schema_version=str(value.get("schema_version") or ""),
        scope=str(value.get("scope") or ""),
    )


def _producer_output_signature(producer: str, value: Any) -> tuple[str, str]:
    normalized_producer = _normalized_producer(producer)
    if not isinstance(value, Mapping):
        return ("", "")
    structured = value.get("structured_info")
    structured = structured if isinstance(structured, Mapping) else {}
    title = str(
        value.get("title")
        or value.get("official_title")
        or structured.get("page_title")
        or structured.get("title")
        or ""
    ).strip()
    url = str(value.get("url") or value.get("official_url") or "").strip()
    return (_title_key(title), _canonical_url(url))


@dataclass(frozen=True)
class CandidateProducerReceipt:
    """Fail-closed proof for one bounded search/fetch operation."""

    producer: str
    plan_fingerprint: str
    operation_id: str
    occurrence: int
    status: str
    input_fingerprint: str
    attempted_count: int
    raw_count: int
    accepted_count: int
    enumeration_finished: bool
    from_cache: bool
    degraded: bool
    possible_throttle: bool
    error_status: str
    output_fingerprint: str
    reason_codes: Tuple[str, ...]
    metadata_fingerprint: str
    schema_version: str = CANDIDATE_PRODUCER_RECEIPT_VERSION
    scope: str = CANDIDATE_PRODUCER_RECEIPT_SCOPE

    def __post_init__(self) -> None:
        producer = _normalized_producer(self.producer)
        object.__setattr__(self, "producer", producer)
        if self.schema_version != CANDIDATE_PRODUCER_RECEIPT_VERSION:
            raise ValueError("unsupported candidate producer receipt schema_version")
        if self.scope != CANDIDATE_PRODUCER_RECEIPT_SCOPE:
            raise ValueError("unsupported candidate producer receipt scope")
        _strict_positive_int(self.occurrence, "occurrence")
        for field_name, value in (
            ("attempted_count", self.attempted_count),
            ("raw_count", self.raw_count),
            ("accepted_count", self.accepted_count),
        ):
            _strict_nonnegative_int(value, field_name)
        if self.accepted_count > self.raw_count:
            raise ValueError("accepted_count exceeds raw_count")
        for field_name, value in (
            ("enumeration_finished", self.enumeration_finished),
            ("from_cache", self.from_cache),
            ("degraded", self.degraded),
            ("possible_throttle", self.possible_throttle),
        ):
            _strict_bool(value, field_name)
        error_status = str(self.error_status or "").strip().upper()
        if error_status not in {
            "NONE",
            "ERROR",
            "EMPTY_RESULT",
            "SKIPPED",
            "MISSING_META",
        }:
            raise ValueError("unsupported candidate producer error_status")
        object.__setattr__(self, "error_status", error_status)
        incomplete = bool(
            not self.enumeration_finished
            or self.attempted_count <= 0
            or self.from_cache
            or self.degraded
            or self.possible_throttle
            or error_status != "NONE"
        )
        expected_status = (
            "UNKNOWN"
            if incomplete
            else "TRUNCATED"
            if self.raw_count > self.accepted_count
            else "COMPLETE"
        )
        status = str(self.status or "").strip().upper()
        object.__setattr__(self, "status", status)
        if status != expected_status:
            raise ValueError("candidate producer receipt status mismatch")
        expected_reasons = [
            "bounded_operation_finished"
            if self.enumeration_finished
            else "bounded_operation_unfinished"
        ]
        if self.from_cache:
            expected_reasons.append("cache_replay")
            expected_reasons.append("cache_origin_proof_missing")
        if self.degraded:
            expected_reasons.append("producer_degraded")
        if self.possible_throttle:
            expected_reasons.append("producer_possible_throttle")
        if error_status == "MISSING_META":
            expected_reasons.append("producer_meta_missing")
        elif error_status == "EMPTY_RESULT":
            expected_reasons.append("producer_empty_result")
        elif error_status == "SKIPPED":
            expected_reasons.append("producer_operation_skipped")
        elif error_status == "ERROR":
            expected_reasons.append("producer_error")
        if expected_status == "TRUNCATED":
            expected_reasons.append("producer_output_truncated")
        normalized_reasons = tuple(
            sorted(
                {
                    str(item or "").strip()
                    for item in self.reason_codes
                    if str(item or "").strip()
                }
            )
        )
        object.__setattr__(self, "reason_codes", normalized_reasons)
        if normalized_reasons != tuple(sorted(expected_reasons)):
            raise ValueError("candidate producer receipt reason_codes mismatch")
        for field_name, value in (
            ("plan_fingerprint", self.plan_fingerprint),
            ("operation_id", self.operation_id),
            ("input_fingerprint", self.input_fingerprint),
            ("output_fingerprint", self.output_fingerprint),
            ("metadata_fingerprint", self.metadata_fingerprint),
        ):
            _require_sha256(value, field_name)
        expected_operation_id = _canonical_hash(
            {
                "schema_version": self.schema_version,
                "plan_fingerprint": self.plan_fingerprint,
                "input_fingerprint": self.input_fingerprint,
                "occurrence": self.occurrence,
            }
        )
        if self.operation_id != expected_operation_id:
            raise ValueError("candidate producer operation_id mismatch")
        if self.metadata_fingerprint != _canonical_hash(
            self.payload_without_metadata_fingerprint()
        ):
            raise ValueError("candidate producer receipt metadata_fingerprint mismatch")

    def payload_without_metadata_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "producer": self.producer,
            "plan_fingerprint": self.plan_fingerprint,
            "operation_id": self.operation_id,
            "occurrence": self.occurrence,
            "status": self.status,
            "input_fingerprint": self.input_fingerprint,
            "attempted_count": self.attempted_count,
            "raw_count": self.raw_count,
            "accepted_count": self.accepted_count,
            "enumeration_finished": self.enumeration_finished,
            "from_cache": self.from_cache,
            "degraded": self.degraded,
            "possible_throttle": self.possible_throttle,
            "error_status": self.error_status,
            "output_fingerprint": self.output_fingerprint,
            "reason_codes": list(self.reason_codes),
        }

    def to_ledger_dict(self) -> dict[str, Any]:
        return {
            **self.payload_without_metadata_fingerprint(),
            "metadata_fingerprint": self.metadata_fingerprint,
        }


def build_candidate_producer_receipt(
    results: Iterable[Any],
    meta: Any,
    *,
    producer: str,
    operation_input: Any,
    purpose: str = "",
    plan_fingerprint: str,
    occurrence: int = 1,
) -> CandidateProducerReceipt:
    normalized_producer = _normalized_producer(producer)
    normalized_plan_fingerprint = _require_sha256(
        plan_fingerprint,
        "plan_fingerprint",
    )
    normalized_occurrence = _strict_positive_int(occurrence, "occurrence")
    result_values = tuple(results)
    meta_map = meta if isinstance(meta, Mapping) else {}
    meta_missing = not isinstance(meta, Mapping) or not meta_map
    input_fingerprint = candidate_producer_input_fingerprint(
        normalized_producer,
        operation_input,
        purpose=purpose,
    )
    attempted_count = 0 if meta_missing else _strict_nonnegative_int(
        int(meta_map.get("attempted_count", meta_map.get("attempts", 1)) or 0),
        "attempted_count",
    )
    accepted_count = len(result_values)
    raw_count_declared = "raw_total" in meta_map or "raw_count" in meta_map
    raw_value = meta_map.get("raw_total", meta_map.get("raw_count", accepted_count))
    try:
        declared_raw_count = int(raw_value or 0)
        raw_count = max(accepted_count, declared_raw_count)
        if raw_count_declared and declared_raw_count < accepted_count:
            meta_missing = True
    except Exception:
        raw_count = accepted_count
        meta_missing = True
    degraded = bool(meta_map.get("degraded"))
    possible_throttle = bool(meta_map.get("possible_throttle"))
    from_cache = bool(meta_map.get("from_cache"))
    raw_error_status = str(meta_map.get("error_status") or "").strip().upper()
    if meta_missing:
        error_status = "MISSING_META"
    elif raw_error_status:
        error_status = raw_error_status
    elif meta_map.get("skipped_reason"):
        error_status = "SKIPPED"
    elif meta_map.get("error"):
        error_status = "ERROR"
    elif normalized_producer == "fetch" and not result_values:
        error_status = "EMPTY_RESULT"
    else:
        error_status = "NONE"
    # Completion must be asserted by the producer. Absence of an error is not
    # evidence that the upstream engine enumerated the bounded operation.
    enumeration_finished = bool(meta_map.get("enumeration_finished", False))
    incomplete = bool(
        not enumeration_finished
        or attempted_count <= 0
        or from_cache
        or degraded
        or possible_throttle
        or error_status != "NONE"
    )
    status = (
        "UNKNOWN"
        if incomplete
        else "TRUNCATED"
        if raw_count > accepted_count
        else "COMPLETE"
    )
    output_signatures = [
        list(signature)
        for signature in (
            _producer_output_signature(normalized_producer, value)
            for value in result_values
        )
        if any(signature)
    ]
    output_fingerprint = _canonical_hash(output_signatures)
    operation_id = _canonical_hash(
        {
            "schema_version": CANDIDATE_PRODUCER_RECEIPT_VERSION,
            "plan_fingerprint": normalized_plan_fingerprint,
            "input_fingerprint": input_fingerprint,
            "occurrence": normalized_occurrence,
        }
    )
    reasons = [
        "bounded_operation_finished"
        if enumeration_finished
        else "bounded_operation_unfinished"
    ]
    if from_cache:
        reasons.append("cache_replay")
        # v1 does not yet bind a replay to the originating receipt/hash.
        # Keep every cache replay UNKNOWN until that provenance exists.
        reasons.append("cache_origin_proof_missing")
    if degraded:
        reasons.append("producer_degraded")
    if possible_throttle:
        reasons.append("producer_possible_throttle")
    if error_status == "MISSING_META":
        reasons.append("producer_meta_missing")
    elif error_status == "EMPTY_RESULT":
        reasons.append("producer_empty_result")
    elif error_status == "SKIPPED":
        reasons.append("producer_operation_skipped")
    elif error_status == "ERROR":
        reasons.append("producer_error")
    if status == "TRUNCATED":
        reasons.append("producer_output_truncated")
    payload = {
        "schema_version": CANDIDATE_PRODUCER_RECEIPT_VERSION,
        "scope": CANDIDATE_PRODUCER_RECEIPT_SCOPE,
        "producer": normalized_producer,
        "plan_fingerprint": normalized_plan_fingerprint,
        "operation_id": operation_id,
        "occurrence": normalized_occurrence,
        "status": status,
        "input_fingerprint": input_fingerprint,
        "attempted_count": attempted_count,
        "raw_count": raw_count,
        "accepted_count": accepted_count,
        "enumeration_finished": enumeration_finished,
        "from_cache": from_cache,
        "degraded": degraded,
        "possible_throttle": possible_throttle,
        "error_status": error_status,
        "output_fingerprint": output_fingerprint,
        "reason_codes": sorted(reasons),
    }
    return CandidateProducerReceipt(
        producer=normalized_producer,
        plan_fingerprint=normalized_plan_fingerprint,
        operation_id=operation_id,
        occurrence=normalized_occurrence,
        status=status,
        input_fingerprint=input_fingerprint,
        attempted_count=attempted_count,
        raw_count=raw_count,
        accepted_count=accepted_count,
        enumeration_finished=enumeration_finished,
        from_cache=from_cache,
        degraded=degraded,
        possible_throttle=possible_throttle,
        error_status=error_status,
        output_fingerprint=output_fingerprint,
        reason_codes=tuple(payload["reason_codes"]),
        metadata_fingerprint=_canonical_hash(payload),
    )


def candidate_producer_receipt_from_dict(value: Any) -> CandidateProducerReceipt:
    if not isinstance(value, Mapping):
        raise ValueError("candidate producer receipt must be an object")
    fields = {str(key) for key in value.keys()}
    if fields != _PRODUCER_RECEIPT_FIELDS:
        missing = sorted(_PRODUCER_RECEIPT_FIELDS - fields)
        extra = sorted(fields - _PRODUCER_RECEIPT_FIELDS)
        raise ValueError(
            f"candidate producer receipt fields mismatch missing={missing} extra={extra}"
        )
    return CandidateProducerReceipt(
        producer=str(value.get("producer") or ""),
        plan_fingerprint=_require_sha256(
            value.get("plan_fingerprint"), "plan_fingerprint"
        ),
        operation_id=_require_sha256(value.get("operation_id"), "operation_id"),
        occurrence=_strict_positive_int(value.get("occurrence"), "occurrence"),
        status=str(value.get("status") or ""),
        input_fingerprint=_require_sha256(
            value.get("input_fingerprint"), "input_fingerprint"
        ),
        attempted_count=_strict_nonnegative_int(
            value.get("attempted_count"), "attempted_count"
        ),
        raw_count=_strict_nonnegative_int(value.get("raw_count"), "raw_count"),
        accepted_count=_strict_nonnegative_int(
            value.get("accepted_count"), "accepted_count"
        ),
        enumeration_finished=_strict_bool(
            value.get("enumeration_finished"), "enumeration_finished"
        ),
        from_cache=_strict_bool(value.get("from_cache"), "from_cache"),
        degraded=_strict_bool(value.get("degraded"), "degraded"),
        possible_throttle=_strict_bool(
            value.get("possible_throttle"), "possible_throttle"
        ),
        error_status=str(value.get("error_status") or ""),
        output_fingerprint=_require_sha256(
            value.get("output_fingerprint"), "output_fingerprint"
        ),
        reason_codes=tuple(
            str(item or "").strip()
            for item in _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        metadata_fingerprint=_require_sha256(
            value.get("metadata_fingerprint"), "metadata_fingerprint"
        ),
        schema_version=str(value.get("schema_version") or ""),
        scope=str(value.get("scope") or ""),
    )


def candidate_producer_receipts_from_payload(
    value: Any,
) -> Tuple[CandidateProducerReceipt, ...]:
    receipts = tuple(
        candidate_producer_receipt_from_dict(item)
        for item in _strict_sequence(value, "candidate_producer_receipts")
    )
    operation_ids = [receipt.operation_id for receipt in receipts]
    if len(operation_ids) != len(set(operation_ids)):
        raise ValueError("duplicate candidate producer operation_id")
    return receipts


def candidate_producer_plans_from_payload(
    value: Any,
) -> Tuple[CandidateProducerPlan, ...]:
    plans = tuple(
        candidate_producer_plan_from_dict(item)
        for item in _strict_sequence(value, "candidate_producer_plans")
    )
    plan_fingerprints = [plan.plan_fingerprint for plan in plans]
    if len(plan_fingerprints) != len(set(plan_fingerprints)):
        raise ValueError("duplicate candidate producer plan_fingerprint")
    identities = [(plan.producer, plan.occurrence) for plan in plans]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate candidate producer plan occurrence")
    return plans


def _proof_expected_reasons(
    *,
    status: str,
    required_producers: Sequence[str],
    observed_producers: Sequence[str],
    planned_operation_count: int,
    unfinished_plan_count: int,
    missing_receipt_count: int,
    extra_receipt_count: int,
    unknown_receipt_count: int,
    truncated_receipt_count: int,
    local_snapshot_count: int,
    local_truncated_count: int,
) -> Tuple[str, ...]:
    reasons = [
        {
            "COMPLETE": "bounded_producer_proof_complete",
            "TRUNCATED": "bounded_producer_proof_truncated",
            "UNKNOWN": "bounded_producer_proof_unknown",
        }[status]
    ]
    if set(required_producers) - set(observed_producers):
        reasons.append("required_producer_missing")
    if planned_operation_count <= 0:
        reasons.append("bounded_plan_empty")
    if unfinished_plan_count:
        reasons.append("bounded_plan_unfinished")
    if missing_receipt_count:
        reasons.append("planned_operation_receipt_missing")
    if extra_receipt_count:
        reasons.append("unplanned_operation_receipt_present")
    if unknown_receipt_count:
        reasons.append("producer_receipt_unknown")
    if truncated_receipt_count:
        reasons.append("producer_receipt_truncated")
    if local_snapshot_count <= 0:
        reasons.append("local_candidate_snapshot_missing")
    if local_truncated_count:
        reasons.append("local_candidate_inventory_truncated")
    return tuple(sorted(reasons))


@dataclass(frozen=True)
class CandidateGenerationProof:
    """Composition proof that may unlock CandidateSet recall evaluation."""

    status: str
    upstream_completeness: str
    required_producers: Tuple[str, ...]
    observed_producers: Tuple[str, ...]
    plan_count: int
    planned_operation_count: int
    receipt_count: int
    complete_receipt_count: int
    unknown_receipt_count: int
    truncated_receipt_count: int
    unfinished_plan_count: int
    missing_receipt_count: int
    extra_receipt_count: int
    local_snapshot_count: int
    local_truncated_count: int
    plan_set_fingerprint: str
    receipt_set_fingerprint: str
    reason_codes: Tuple[str, ...]
    metadata_fingerprint: str
    schema_version: str = CANDIDATE_GENERATION_PROOF_VERSION
    scope: str = CANDIDATE_GENERATION_PROOF_SCOPE

    def __post_init__(self) -> None:
        if self.schema_version != CANDIDATE_GENERATION_PROOF_VERSION:
            raise ValueError("unsupported candidate generation proof schema_version")
        if self.scope != CANDIDATE_GENERATION_PROOF_SCOPE:
            raise ValueError("unsupported candidate generation proof scope")
        status = str(self.status or "").strip().upper()
        if status not in {"COMPLETE", "TRUNCATED", "UNKNOWN"}:
            raise ValueError("unsupported candidate generation proof status")
        object.__setattr__(self, "status", status)
        expected_upstream = "COMPLETE" if status == "COMPLETE" else "UNKNOWN"
        if self.upstream_completeness != expected_upstream:
            raise ValueError("candidate generation proof upstream_completeness mismatch")
        required = tuple(sorted({_normalized_producer(item) for item in self.required_producers}))
        observed = tuple(sorted({_normalized_producer(item) for item in self.observed_producers}))
        if required != CANDIDATE_REQUIRED_PRODUCERS:
            raise ValueError("candidate generation proof required_producers mismatch")
        object.__setattr__(self, "required_producers", required)
        object.__setattr__(self, "observed_producers", observed)
        for field_name in (
            "plan_count",
            "planned_operation_count",
            "receipt_count",
            "complete_receipt_count",
            "unknown_receipt_count",
            "truncated_receipt_count",
            "unfinished_plan_count",
            "missing_receipt_count",
            "extra_receipt_count",
            "local_snapshot_count",
            "local_truncated_count",
        ):
            _strict_nonnegative_int(getattr(self, field_name), field_name)
        if (
            self.complete_receipt_count
            + self.unknown_receipt_count
            + self.truncated_receipt_count
            != self.receipt_count
        ):
            raise ValueError("candidate generation proof receipt status counts mismatch")
        if self.local_truncated_count > self.local_snapshot_count:
            raise ValueError("local_truncated_count exceeds local_snapshot_count")
        truncated = bool(
            self.truncated_receipt_count or self.local_truncated_count
        )
        unknown = bool(
            set(required) - set(observed)
            or self.planned_operation_count <= 0
            or self.unfinished_plan_count
            or self.missing_receipt_count
            or self.extra_receipt_count
            or self.unknown_receipt_count
            or self.local_snapshot_count <= 0
        )
        expected_status = "TRUNCATED" if truncated else "UNKNOWN" if unknown else "COMPLETE"
        if status != expected_status:
            raise ValueError("candidate generation proof status/count mismatch")
        expected_reasons = _proof_expected_reasons(
            status=status,
            required_producers=required,
            observed_producers=observed,
            planned_operation_count=self.planned_operation_count,
            unfinished_plan_count=self.unfinished_plan_count,
            missing_receipt_count=self.missing_receipt_count,
            extra_receipt_count=self.extra_receipt_count,
            unknown_receipt_count=self.unknown_receipt_count,
            truncated_receipt_count=self.truncated_receipt_count,
            local_snapshot_count=self.local_snapshot_count,
            local_truncated_count=self.local_truncated_count,
        )
        normalized_reasons = tuple(
            sorted(
                {
                    str(item or "").strip()
                    for item in self.reason_codes
                    if str(item or "").strip()
                }
            )
        )
        object.__setattr__(self, "reason_codes", normalized_reasons)
        if normalized_reasons != expected_reasons:
            raise ValueError("candidate generation proof reason_codes mismatch")
        for field_name, value in (
            ("plan_set_fingerprint", self.plan_set_fingerprint),
            ("receipt_set_fingerprint", self.receipt_set_fingerprint),
            ("metadata_fingerprint", self.metadata_fingerprint),
        ):
            _require_sha256(value, field_name)
        if self.metadata_fingerprint != _canonical_hash(
            self.payload_without_metadata_fingerprint()
        ):
            raise ValueError("candidate generation proof metadata_fingerprint mismatch")

    def payload_without_metadata_fingerprint(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "status": self.status,
            "upstream_completeness": self.upstream_completeness,
            "required_producers": list(self.required_producers),
            "observed_producers": list(self.observed_producers),
            "plan_count": self.plan_count,
            "planned_operation_count": self.planned_operation_count,
            "receipt_count": self.receipt_count,
            "complete_receipt_count": self.complete_receipt_count,
            "unknown_receipt_count": self.unknown_receipt_count,
            "truncated_receipt_count": self.truncated_receipt_count,
            "unfinished_plan_count": self.unfinished_plan_count,
            "missing_receipt_count": self.missing_receipt_count,
            "extra_receipt_count": self.extra_receipt_count,
            "local_snapshot_count": self.local_snapshot_count,
            "local_truncated_count": self.local_truncated_count,
            "plan_set_fingerprint": self.plan_set_fingerprint,
            "receipt_set_fingerprint": self.receipt_set_fingerprint,
            "reason_codes": list(self.reason_codes),
        }

    def to_ledger_dict(self) -> dict[str, Any]:
        return {
            **self.payload_without_metadata_fingerprint(),
            "metadata_fingerprint": self.metadata_fingerprint,
        }


def build_candidate_generation_proof(
    plans: Iterable[Any],
    receipts: Iterable[Any],
    *,
    local_snapshots: Iterable[Any],
    required_producers: Iterable[str] = ("search", "fetch"),
) -> CandidateGenerationProof:
    normalized_plans = tuple(
        item
        if isinstance(item, CandidateProducerPlan)
        else candidate_producer_plan_from_dict(item)
        for item in tuple(plans)
    )
    normalized_receipts = tuple(
        item
        if isinstance(item, CandidateProducerReceipt)
        else candidate_producer_receipt_from_dict(item)
        for item in tuple(receipts)
    )
    candidate_producer_plans_from_payload(
        [item.to_ledger_dict() for item in normalized_plans]
    )
    candidate_producer_receipts_from_payload(
        [item.to_ledger_dict() for item in normalized_receipts]
    )
    required = tuple(sorted({_normalized_producer(item) for item in required_producers}))
    if required != CANDIDATE_REQUIRED_PRODUCERS:
        raise ValueError(
            "candidate generation proof requires canonical search+fetch producers"
        )
    # A required producer with an empty plan is not evidence that the producer
    # participated. Treat it as missing so a search-only plan plus an empty
    # fetch placeholder cannot manufacture COMPLETE.
    observed = tuple(
        sorted(
            {
                plan.producer
                for plan in normalized_plans
                if plan.planned_operation_fingerprints
            }
        )
    )
    planned_pairs = Counter(
        (plan.plan_fingerprint, input_fingerprint)
        for plan in normalized_plans
        for input_fingerprint in plan.planned_operation_fingerprints
    )
    receipt_pairs = Counter(
        (receipt.plan_fingerprint, receipt.input_fingerprint)
        for receipt in normalized_receipts
    )
    missing_count = sum((planned_pairs - receipt_pairs).values())
    extra_count = sum((receipt_pairs - planned_pairs).values())
    status_counts = Counter(receipt.status for receipt in normalized_receipts)
    local_statuses: list[str] = []
    for item in tuple(local_snapshots):
        if isinstance(item, CandidateGenerationSnapshot):
            status = item.status
        elif isinstance(item, Mapping):
            status = str(item.get("status") or "").strip().upper()
        else:
            status = str(item or "").strip().upper()
        if status not in {"UNKNOWN", "TRUNCATED", "COMPLETE"}:
            raise ValueError("unsupported local candidate snapshot status")
        local_statuses.append(status)
    local_truncated_count = sum(status == "TRUNCATED" for status in local_statuses)
    truncated = bool(status_counts["TRUNCATED"] or local_truncated_count)
    unknown = bool(
        set(required) - set(observed)
        or not planned_pairs
        or any(not plan.enumeration_finished for plan in normalized_plans)
        or missing_count
        or extra_count
        or status_counts["UNKNOWN"]
        or not local_statuses
    )
    status = "TRUNCATED" if truncated else "UNKNOWN" if unknown else "COMPLETE"
    payload = {
        "schema_version": CANDIDATE_GENERATION_PROOF_VERSION,
        "scope": CANDIDATE_GENERATION_PROOF_SCOPE,
        "status": status,
        "upstream_completeness": "COMPLETE" if status == "COMPLETE" else "UNKNOWN",
        "required_producers": list(required),
        "observed_producers": list(observed),
        "plan_count": len(normalized_plans),
        "planned_operation_count": sum(planned_pairs.values()),
        "receipt_count": len(normalized_receipts),
        "complete_receipt_count": status_counts["COMPLETE"],
        "unknown_receipt_count": status_counts["UNKNOWN"],
        "truncated_receipt_count": status_counts["TRUNCATED"],
        "unfinished_plan_count": sum(
            not plan.enumeration_finished for plan in normalized_plans
        ),
        "missing_receipt_count": missing_count,
        "extra_receipt_count": extra_count,
        "local_snapshot_count": len(local_statuses),
        "local_truncated_count": local_truncated_count,
        "plan_set_fingerprint": _canonical_hash(
            sorted(plan.metadata_fingerprint for plan in normalized_plans)
        ),
        "receipt_set_fingerprint": _canonical_hash(
            sorted(receipt.metadata_fingerprint for receipt in normalized_receipts)
        ),
    }
    payload["reason_codes"] = list(
        _proof_expected_reasons(
            status=status,
            required_producers=required,
            observed_producers=observed,
            planned_operation_count=payload["planned_operation_count"],
            unfinished_plan_count=payload["unfinished_plan_count"],
            missing_receipt_count=missing_count,
            extra_receipt_count=extra_count,
            unknown_receipt_count=status_counts["UNKNOWN"],
            truncated_receipt_count=status_counts["TRUNCATED"],
            local_snapshot_count=len(local_statuses),
            local_truncated_count=local_truncated_count,
        )
    )
    return CandidateGenerationProof(
        status=status,
        upstream_completeness=payload["upstream_completeness"],
        required_producers=required,
        observed_producers=observed,
        plan_count=payload["plan_count"],
        planned_operation_count=payload["planned_operation_count"],
        receipt_count=payload["receipt_count"],
        complete_receipt_count=payload["complete_receipt_count"],
        unknown_receipt_count=payload["unknown_receipt_count"],
        truncated_receipt_count=payload["truncated_receipt_count"],
        unfinished_plan_count=payload["unfinished_plan_count"],
        missing_receipt_count=missing_count,
        extra_receipt_count=extra_count,
        local_snapshot_count=payload["local_snapshot_count"],
        local_truncated_count=local_truncated_count,
        plan_set_fingerprint=payload["plan_set_fingerprint"],
        receipt_set_fingerprint=payload["receipt_set_fingerprint"],
        reason_codes=tuple(payload["reason_codes"]),
        metadata_fingerprint=_canonical_hash(payload),
    )


def candidate_generation_proof_from_dict(value: Any) -> CandidateGenerationProof:
    if not isinstance(value, Mapping):
        raise ValueError("candidate generation proof must be an object")
    fields = {str(key) for key in value.keys()}
    if fields != _GENERATION_PROOF_FIELDS:
        missing = sorted(_GENERATION_PROOF_FIELDS - fields)
        extra = sorted(fields - _GENERATION_PROOF_FIELDS)
        raise ValueError(
            f"candidate generation proof fields mismatch missing={missing} extra={extra}"
        )
    return CandidateGenerationProof(
        status=str(value.get("status") or ""),
        upstream_completeness=str(value.get("upstream_completeness") or ""),
        required_producers=tuple(
            str(item or "").strip()
            for item in _strict_sequence(
                value.get("required_producers"), "required_producers"
            )
        ),
        observed_producers=tuple(
            str(item or "").strip()
            for item in _strict_sequence(
                value.get("observed_producers"), "observed_producers"
            )
        ),
        plan_count=_strict_nonnegative_int(value.get("plan_count"), "plan_count"),
        planned_operation_count=_strict_nonnegative_int(
            value.get("planned_operation_count"), "planned_operation_count"
        ),
        receipt_count=_strict_nonnegative_int(
            value.get("receipt_count"), "receipt_count"
        ),
        complete_receipt_count=_strict_nonnegative_int(
            value.get("complete_receipt_count"), "complete_receipt_count"
        ),
        unknown_receipt_count=_strict_nonnegative_int(
            value.get("unknown_receipt_count"), "unknown_receipt_count"
        ),
        truncated_receipt_count=_strict_nonnegative_int(
            value.get("truncated_receipt_count"), "truncated_receipt_count"
        ),
        unfinished_plan_count=_strict_nonnegative_int(
            value.get("unfinished_plan_count"), "unfinished_plan_count"
        ),
        missing_receipt_count=_strict_nonnegative_int(
            value.get("missing_receipt_count"), "missing_receipt_count"
        ),
        extra_receipt_count=_strict_nonnegative_int(
            value.get("extra_receipt_count"), "extra_receipt_count"
        ),
        local_snapshot_count=_strict_nonnegative_int(
            value.get("local_snapshot_count"), "local_snapshot_count"
        ),
        local_truncated_count=_strict_nonnegative_int(
            value.get("local_truncated_count"), "local_truncated_count"
        ),
        plan_set_fingerprint=_require_sha256(
            value.get("plan_set_fingerprint"), "plan_set_fingerprint"
        ),
        receipt_set_fingerprint=_require_sha256(
            value.get("receipt_set_fingerprint"), "receipt_set_fingerprint"
        ),
        reason_codes=tuple(
            str(item or "").strip()
            for item in _strict_sequence(value.get("reason_codes"), "reason_codes")
        ),
        metadata_fingerprint=_require_sha256(
            value.get("metadata_fingerprint"), "metadata_fingerprint"
        ),
        schema_version=str(value.get("schema_version") or ""),
        scope=str(value.get("scope") or ""),
    )
