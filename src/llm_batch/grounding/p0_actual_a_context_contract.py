"""실제 P0 Track-A 문맥 리뷰의 fail-close 계약.

이 모듈은 source registry의 Track-A claim, A-context, 사람 annotation event를
구조적으로 결속한다. 구조 검증은 실제 수집 권한, reviewer assignment,
guideline authority, append-only 외부 앵커를 증명하지 않는다. 따라서 정상 검증된
row도 actual 20건 credit, publication, Slang DB/WAL 쓰기를 열지 않는다.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .p0_actual_registry_contract import (
    ACTUAL_ORIGIN,
    EXAMPLE_ORIGIN,
    OPERATIONAL_EFFECT,
    P0ActualContractError,
    _validate_source_claim,
)


A_CONTEXT_SCHEMA = "p0_actual_a_context_v1"
A_ANNOTATION_EVENT_SCHEMA = "p0_actual_a_annotation_event_v1"
A_CONTEXT_RECEIPT_SCHEMA = "p0_actual_a_context_validation_receipt_v1"

A_TRUTH_KINDS = ("WORK_ID", "NIL", "UNRESOLVED")
ANNOTATION_STATUSES = ("JUDGED", "UNJUDGED", "UNAVAILABLE")

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRUTH_REASONS = {
    "truth_direct_official_id",
    "truth_explicit_alias_relation",
    "truth_context_work_relation",
    "truth_nil_non_work",
    "truth_nil_out_of_universe",
    "truth_nil_no_canonical_target_after_complete_enumeration",
}
_ANNOTATION_REASONS = {
    "annotation_human_review_completed",
    "annotation_alias_sense_unresolved",
    "annotation_multiwork_primary_unresolved",
    "annotation_conflicting_evidence",
    "annotation_insufficient_context",
    "evidence_unavailable",
    "evidence_access_restricted",
    "evidence_deleted",
}
_NIL_REASONS = {
    "NIL_NON_WORK",
    "NIL_OUT_OF_UNIVERSE",
    "NIL_NO_VALID_CANDIDATE",
}

_A_CONTEXT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "context_id",
        "sampling_frame_sha256",
        "sampling_unit_id",
        "sampling_unit_sha256",
        "post_id",
        "content_text",
        "content_fingerprint",
        "context_observed_at",
        "surface_text",
        "surface_start",
        "surface_end",
        "surface_sha256",
        "normalized_surface",
        "community_scope",
        "platform_scope",
        "candidate_work_ids",
        "candidate_set_fingerprint",
        "candidate_registry_snapshot_sha256",
        "candidate_registry_status",
        "source_claim_ids",
        "source_claim_set_sha256",
        "evidence_cutoff",
        "evidence_receipt_sha256",
        "annotation_subject_sha256",
        "annotation_status",
        "truth_kind",
        "truth_work_id",
        "truth_nil_reason",
        "truth_reason_codes",
        "annotation_reason_codes",
        "latest_annotation_event_id",
        "latest_annotation_event_sha256",
        "reviewer_principal_sha256",
        "reviewer_assignment_receipt_sha256",
        "guideline_path",
        "guideline_version",
        "guideline_sha256",
        "action_applied",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "operational_effect",
        "row_sha256",
    }
)

_A_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "journal_id",
        "journal_sequence",
        "event_id",
        "event_sha256",
        "previous_event_id",
        "previous_event_sha256",
        "target_record_type",
        "target_id",
        "target_subject_sha256",
        "reviewer_pseudonym_sha256",
        "reviewer_principal_sha256",
        "reviewer_role",
        "independent_review",
        "reviewer_assignment_receipt_sha256",
        "guideline_path",
        "guideline_version",
        "guideline_sha256",
        "event_kind",
        "supersedes_event_ids",
        "occurred_at",
        "evidence_cutoff",
        "evidence_claim_ids",
        "annotation_status",
        "decision_kind",
        "decision_work_id",
        "decision_nil_reason",
        "decision_payload_sha256",
        "truth_reason_codes",
        "annotation_reason_codes",
        "action_applied",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "operational_effect",
        "row_sha256",
    }
)


class P0ActualAContextContractError(P0ActualContractError):
    """A-context 계약이 구조적 또는 의미적 결속을 잃었을 때 발생한다."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def with_row_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("row_sha256", None)
    return {**material, "row_sha256": canonical_sha256(material)}


def _strict(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualAContextContractError(f"{label} must be an object")
    if set(value) != fields:
        raise P0ActualAContextContractError(
            f"{label} fields mismatch: missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise P0ActualAContextContractError(f"{field} must be canonical non-empty text")
    return value


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P0ActualAContextContractError(f"{field} must be non-empty text")
    return value


def _optional_text(value: Any, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualAContextContractError(f"{field} must be lowercase sha256")
    return value


def _optional_sha(value: Any, field: str) -> str | None:
    return None if value is None else _sha(value, field)


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0ActualAContextContractError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0ActualAContextContractError(f"{field} must include timezone")
    return parsed


def _sorted_texts(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise P0ActualAContextContractError(f"{field} must be a list")
    result = [_text(item, field) for item in value]
    if result != sorted(result) or len(result) != len(set(result)):
        raise P0ActualAContextContractError(f"{field} must be sorted and unique")
    if not allow_empty and not result:
        raise P0ActualAContextContractError(f"{field} must not be empty")
    return result


def _reasons(
    value: Any,
    field: str,
    allowed: set[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    result = _sorted_texts(value, field, allow_empty=allow_empty)
    unknown = sorted(set(result) - allowed)
    if unknown:
        raise P0ActualAContextContractError(
            f"{field} contains unregistered codes: {unknown}"
        )
    return result


def _origin(row: Mapping[str, Any], expected_origin: str) -> None:
    if expected_origin not in {ACTUAL_ORIGIN, EXAMPLE_ORIGIN}:
        raise P0ActualAContextContractError("unsupported record origin")
    if row["record_origin"] != expected_origin:
        raise P0ActualAContextContractError("actual/example origin namespace mismatch")


def _self_hash(row: Mapping[str, Any], digest_field: str, label: str) -> None:
    stored = _sha(row[digest_field], digest_field)
    material = {key: item for key, item in row.items() if key != digest_field}
    if stored != canonical_sha256(material):
        raise P0ActualAContextContractError(f"{label} hash mismatch")


def sampling_unit_sha256(row: Mapping[str, Any]) -> str:
    """caller-issued ID를 제외한 논리적 문맥 단위를 고정한다.

    context/post/sampling ID만 재발급해 같은 본문·span을 분모에 여러 번 넣는
    것을 막는다. 서로 다른 독립 원문을 주장하려면 content fingerprint가
    실제로 달라야 하며, 외부 sampling-frame authority는 별도 gate다.
    """
    return canonical_sha256(
        {
            "platform_scope": row["platform_scope"],
            "community_scope": row["community_scope"],
            "content_fingerprint": row["content_fingerprint"],
            "surface_start": row["surface_start"],
            "surface_end": row["surface_end"],
            "surface_sha256": row["surface_sha256"],
        }
    )


def source_claim_set_sha256(claim_rows: Sequence[Mapping[str, Any]]) -> str:
    """A-context가 인용한 source claim의 불변 집합 digest를 만든다."""
    return canonical_sha256(
        [
            {
                "claim_id": row["claim_id"],
                "row_sha256": row["row_sha256"],
                "claim_evidence_receipt_sha256": row[
                    "claim_evidence_receipt_sha256"
                ],
            }
            for row in sorted(claim_rows, key=lambda item: item["claim_id"])
        ]
    )


def evidence_receipt_sha256(row: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "sampling_unit_sha256": row["sampling_unit_sha256"],
            "source_claim_ids": row["source_claim_ids"],
            "source_claim_set_sha256": row["source_claim_set_sha256"],
            "evidence_cutoff": row["evidence_cutoff"],
            "candidate_work_ids": row["candidate_work_ids"],
            "candidate_set_fingerprint": row["candidate_set_fingerprint"],
            "candidate_registry_snapshot_sha256": row[
                "candidate_registry_snapshot_sha256"
            ],
            "candidate_registry_status": row["candidate_registry_status"],
        }
    )


def annotation_subject_sha256(row: Mapping[str, Any]) -> str:
    """사람 판단 전에 고정되어야 하는 A-context subject를 계산한다."""
    return canonical_sha256(
        {
            "context_id": row["context_id"],
            "sampling_unit_sha256": row["sampling_unit_sha256"],
            "post_id": row["post_id"],
            "content_fingerprint": row["content_fingerprint"],
            "context_observed_at": row["context_observed_at"],
            "surface_text": row["surface_text"],
            "surface_start": row["surface_start"],
            "surface_end": row["surface_end"],
            "surface_sha256": row["surface_sha256"],
            "normalized_surface": row["normalized_surface"],
            "community_scope": row["community_scope"],
            "platform_scope": row["platform_scope"],
            "candidate_work_ids": row["candidate_work_ids"],
            "candidate_set_fingerprint": row["candidate_set_fingerprint"],
            "candidate_registry_snapshot_sha256": row[
                "candidate_registry_snapshot_sha256"
            ],
            "candidate_registry_status": row["candidate_registry_status"],
            "source_claim_ids": row["source_claim_ids"],
            "source_claim_set_sha256": row["source_claim_set_sha256"],
            "evidence_cutoff": row["evidence_cutoff"],
            "evidence_receipt_sha256": row["evidence_receipt_sha256"],
        }
    )


def decision_payload_sha256(row: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "annotation_status": row["annotation_status"],
            "decision_kind": row.get("decision_kind", row.get("truth_kind")),
            "decision_work_id": row.get("decision_work_id", row.get("truth_work_id")),
            "decision_nil_reason": row.get(
                "decision_nil_reason", row.get("truth_nil_reason")
            ),
            "truth_reason_codes": row["truth_reason_codes"],
            "annotation_reason_codes": row["annotation_reason_codes"],
        }
    )


def annotation_event_sha256(row: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            key: item
            for key, item in row.items()
            if key not in {"event_sha256", "row_sha256"}
        }
    )


def _validate_no_write(row: Mapping[str, Any], label: str) -> None:
    if (
        row["action_applied"] is not False
        or row["public_apply"] is not False
        or row["central_slang_db_write"] is not False
        or row["publication_wal_write"] is not False
        or row["operational_effect"] != OPERATIONAL_EFFECT
    ):
        raise P0ActualAContextContractError(f"{label} must be no-write shadow only")


def _validate_decision(
    row: Mapping[str, Any],
    *,
    kind_field: str,
    work_field: str,
    nil_field: str,
) -> None:
    status = row["annotation_status"]
    kind = row[kind_field]
    work_id = _optional_text(row[work_field], work_field)
    nil_reason = _optional_text(row[nil_field], nil_field)
    truth_reasons = _reasons(
        row["truth_reason_codes"], "truth_reason_codes", _TRUTH_REASONS, allow_empty=True
    )
    annotation_reasons = _reasons(
        row["annotation_reason_codes"],
        "annotation_reason_codes",
        _ANNOTATION_REASONS,
    )
    if status not in ANNOTATION_STATUSES or kind not in A_TRUTH_KINDS:
        raise P0ActualAContextContractError("A annotation status/decision is invalid")
    if status == "JUDGED":
        if kind not in {"WORK_ID", "NIL"} or not truth_reasons:
            raise P0ActualAContextContractError("JUDGED A decision must be terminal")
        if annotation_reasons != ["annotation_human_review_completed"]:
            raise P0ActualAContextContractError("JUDGED annotation reason mismatch")
    else:
        allowed = (
            {
                "annotation_alias_sense_unresolved",
                "annotation_multiwork_primary_unresolved",
                "annotation_conflicting_evidence",
                "annotation_insufficient_context",
            }
            if status == "UNJUDGED"
            else {"evidence_unavailable", "evidence_access_restricted", "evidence_deleted"}
        )
        if kind != "UNRESOLVED" or work_id is not None or nil_reason is not None:
            raise P0ActualAContextContractError(
                "non-judged A decision must remain UNRESOLVED"
            )
        if truth_reasons or not set(annotation_reasons).issubset(allowed):
            raise P0ActualAContextContractError("A status/reason family mismatch")
    if kind == "WORK_ID":
        if work_id is None or nil_reason is not None or not set(truth_reasons).issubset(
            {
                "truth_direct_official_id",
                "truth_explicit_alias_relation",
                "truth_context_work_relation",
            }
        ):
            raise P0ActualAContextContractError("WORK_ID decision binding mismatch")
    elif kind == "NIL":
        expected_reason = {
            "NIL_NON_WORK": "truth_nil_non_work",
            "NIL_OUT_OF_UNIVERSE": "truth_nil_out_of_universe",
            "NIL_NO_VALID_CANDIDATE": "truth_nil_no_canonical_target_after_complete_enumeration",
        }.get(nil_reason)
        if work_id is not None or nil_reason not in _NIL_REASONS or truth_reasons != [expected_reason]:
            raise P0ActualAContextContractError("NIL decision binding mismatch")


def _validate_a_context(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _A_CONTEXT_FIELDS, "A context")
    if row["schema_version"] != A_CONTEXT_SCHEMA:
        raise P0ActualAContextContractError("A context schema mismatch")
    _origin(row, expected_origin)
    for field in (
        "context_id",
        "sampling_unit_id",
        "post_id",
        "surface_text",
        "normalized_surface",
        "community_scope",
        "platform_scope",
        "latest_annotation_event_id",
        "guideline_path",
        "guideline_version",
    ):
        _text(row[field], field)
    _nonempty_text(row["content_text"], "content_text")
    if _sha(row["content_fingerprint"], "content_fingerprint") != canonical_sha256(
        row["content_text"]
    ):
        raise P0ActualAContextContractError("A content_fingerprint mismatch")
    _sha(row["sampling_frame_sha256"], "sampling_frame_sha256")
    _sha(row["surface_sha256"], "surface_sha256")
    if _sha(row["sampling_unit_sha256"], "sampling_unit_sha256") != sampling_unit_sha256(row):
        raise P0ActualAContextContractError("sampling unit binding mismatch")
    for field in ("surface_start", "surface_end"):
        item = row[field]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise P0ActualAContextContractError(f"{field} is invalid")
    if (
        row["surface_end"] <= row["surface_start"]
        or row["surface_end"] > len(row["content_text"])
        or row["content_text"][row["surface_start"] : row["surface_end"]]
        != row["surface_text"]
        or row["surface_sha256"] != canonical_sha256(row["surface_text"])
    ):
        raise P0ActualAContextContractError("A surface span/hash mismatch")
    observed = _timestamp(row["context_observed_at"], "context_observed_at")
    cutoff = _timestamp(row["evidence_cutoff"], "evidence_cutoff")
    if cutoff > observed:
        raise P0ActualAContextContractError("evidence cutoff must not follow observation")
    candidates = _sorted_texts(
        row["candidate_work_ids"], "candidate_work_ids", allow_empty=True
    )
    if row["candidate_registry_status"] not in {"COMPLETE", "INCOMPLETE", "UNAVAILABLE"}:
        raise P0ActualAContextContractError("candidate_registry_status is invalid")
    if row["candidate_registry_status"] == "UNAVAILABLE" and candidates:
        raise P0ActualAContextContractError("unavailable candidate registry must be empty")
    if _sha(
        row["candidate_set_fingerprint"], "candidate_set_fingerprint"
    ) != canonical_sha256(candidates):
        raise P0ActualAContextContractError("candidate set fingerprint mismatch")
    _sha(row["candidate_registry_snapshot_sha256"], "candidate_registry_snapshot_sha256")
    _sorted_texts(row["source_claim_ids"], "source_claim_ids")
    _sha(row["source_claim_set_sha256"], "source_claim_set_sha256")
    if _sha(row["evidence_receipt_sha256"], "evidence_receipt_sha256") != evidence_receipt_sha256(row):
        raise P0ActualAContextContractError("A evidence receipt binding mismatch")
    if _sha(row["annotation_subject_sha256"], "annotation_subject_sha256") != annotation_subject_sha256(row):
        raise P0ActualAContextContractError("A annotation subject binding mismatch")
    _validate_decision(
        row,
        kind_field="truth_kind",
        work_field="truth_work_id",
        nil_field="truth_nil_reason",
    )
    if row["truth_kind"] == "WORK_ID":
        if row["candidate_registry_status"] != "COMPLETE" or row["truth_work_id"] not in candidates:
            raise P0ActualAContextContractError("WORK_ID requires a complete bound candidate")
    if row["truth_kind"] == "NIL" and row["candidate_registry_status"] != "COMPLETE":
        raise P0ActualAContextContractError("NIL requires complete candidate enumeration")
    if row["annotation_status"] == "UNAVAILABLE" and row["candidate_registry_status"] != "UNAVAILABLE":
        raise P0ActualAContextContractError("UNAVAILABLE review must fail closed")
    for field in (
        "latest_annotation_event_sha256",
        "reviewer_principal_sha256",
        "reviewer_assignment_receipt_sha256",
        "guideline_sha256",
    ):
        _sha(row[field], field)
    _validate_no_write(row, "A context")
    _self_hash(row, "row_sha256", "A context")
    return dict(row)


def validate_actual_a_context(value: Any) -> dict[str, Any]:
    """actual-origin A-context 한 건을 검증하되 authority는 부여하지 않는다."""
    return _validate_a_context(value, ACTUAL_ORIGIN)


def validate_example_a_context(value: Any) -> dict[str, Any]:
    """contract-example A-context 한 건을 실제 관측값과 분리 검증한다."""
    return _validate_a_context(value, EXAMPLE_ORIGIN)


def _validate_a_event(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _A_EVENT_FIELDS, "A annotation event")
    if row["schema_version"] != A_ANNOTATION_EVENT_SCHEMA:
        raise P0ActualAContextContractError("A annotation event schema mismatch")
    _origin(row, expected_origin)
    for field in (
        "journal_id",
        "event_id",
        "target_id",
        "reviewer_role",
        "guideline_path",
        "guideline_version",
    ):
        _text(row[field], field)
    sequence = row["journal_sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise P0ActualAContextContractError("journal_sequence is invalid")
    previous_id = _optional_text(row["previous_event_id"], "previous_event_id")
    previous_sha = _optional_sha(row["previous_event_sha256"], "previous_event_sha256")
    if (sequence == 1) != (previous_id is None and previous_sha is None):
        raise P0ActualAContextContractError("A annotation previous-event binding mismatch")
    if row["target_record_type"] != "A_CONTEXT":
        raise P0ActualAContextContractError("A event target type must be A_CONTEXT")
    for field in (
        "target_subject_sha256",
        "reviewer_pseudonym_sha256",
        "reviewer_principal_sha256",
        "reviewer_assignment_receipt_sha256",
        "guideline_sha256",
    ):
        _sha(row[field], field)
    if row["reviewer_role"] != "HUMAN_CURATOR" or not isinstance(
        row["independent_review"], bool
    ):
        raise P0ActualAContextContractError("A event requires a human curator")
    supersedes = _sorted_texts(
        row["supersedes_event_ids"], "supersedes_event_ids", allow_empty=True
    )
    if row["event_kind"] == "PRIMARY_REVIEW":
        if supersedes or row["independent_review"] is not True:
            raise P0ActualAContextContractError("primary A review must be independent")
    elif row["event_kind"] == "INTRA_RATER_RECHECK":
        if not supersedes or row["independent_review"] is not False:
            raise P0ActualAContextContractError("A recheck must supersede an earlier vote")
    else:
        raise P0ActualAContextContractError("A event_kind is invalid")
    occurred = _timestamp(row["occurred_at"], "occurred_at")
    cutoff = _timestamp(row["evidence_cutoff"], "evidence_cutoff")
    if cutoff > occurred:
        raise P0ActualAContextContractError("A event evidence cutoff must not follow event")
    _sorted_texts(row["evidence_claim_ids"], "evidence_claim_ids")
    _validate_decision(
        row,
        kind_field="decision_kind",
        work_field="decision_work_id",
        nil_field="decision_nil_reason",
    )
    if _sha(row["decision_payload_sha256"], "decision_payload_sha256") != decision_payload_sha256(row):
        raise P0ActualAContextContractError("A event decision payload mismatch")
    _validate_no_write(row, "A annotation event")
    if _sha(row["event_sha256"], "event_sha256") != annotation_event_sha256(row):
        raise P0ActualAContextContractError("A annotation event hash mismatch")
    _self_hash(row, "row_sha256", "A annotation event")
    return dict(row)


def validate_actual_a_annotation_event(value: Any) -> dict[str, Any]:
    return _validate_a_event(value, ACTUAL_ORIGIN)


def validate_example_a_annotation_event(value: Any) -> dict[str, Any]:
    return _validate_a_event(value, EXAMPLE_ORIGIN)


def _validate_event_chains(events: Sequence[Mapping[str, Any]]) -> None:
    by_id = {row["event_id"]: row for row in events}
    if len(by_id) != len(events):
        raise P0ActualAContextContractError("A annotation event_id must be unique")
    by_journal: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in events:
        by_journal[row["journal_id"]].append(row)
    for rows in by_journal.values():
        ordered = sorted(rows, key=lambda item: item["journal_sequence"])
        if len({row["target_id"] for row in ordered}) != 1:
            raise P0ActualAContextContractError(
                "A review journal must belong to one context"
            )
        if [row["journal_sequence"] for row in ordered] != list(range(1, len(rows) + 1)):
            raise P0ActualAContextContractError("A journal sequence must be contiguous")
        if ordered[0]["event_kind"] != "PRIMARY_REVIEW" or any(
            row["event_kind"] != "INTRA_RATER_RECHECK" for row in ordered[1:]
        ):
            raise P0ActualAContextContractError(
                "A journal must start with one primary review and continue with rechecks"
            )
        for previous, current in zip(ordered, ordered[1:]):
            if (
                current["previous_event_id"] != previous["event_id"]
                or current["previous_event_sha256"] != previous["event_sha256"]
                or _timestamp(current["occurred_at"], "occurred_at")
                <= _timestamp(previous["occurred_at"], "occurred_at")
            ):
                raise P0ActualAContextContractError("A annotation hash chain mismatch")
            for event_id in current["supersedes_event_ids"]:
                superseded = by_id.get(event_id)
                if (
                    superseded is None
                    or superseded["target_id"] != current["target_id"]
                    or superseded["journal_id"] != current["journal_id"]
                    or superseded["journal_sequence"] >= current["journal_sequence"]
                ):
                    raise P0ActualAContextContractError("invalid A supersession target")


def _validate_bundle(
    source_claims: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str,
) -> dict[str, Any]:
    if not source_claims or not contexts or not events:
        raise P0ActualAContextContractError("A bundle inputs must not be empty")
    try:
        claims = [
            _validate_source_claim(row, expected_origin) for row in source_claims
        ]
    except P0ActualContractError as exc:
        raise P0ActualAContextContractError(str(exc)) from exc
    validated_contexts = [_validate_a_context(row, expected_origin) for row in contexts]
    validated_events = [_validate_a_event(row, expected_origin) for row in events]
    if any(row["track"] != "A" for row in claims):
        raise P0ActualAContextContractError("A context bundle accepts TRACK A claims only")
    by_claim = {row["claim_id"]: row for row in claims}
    if len(by_claim) != len(claims):
        raise P0ActualAContextContractError("A source claim_id must be unique")
    for field in ("context_id", "sampling_unit_id", "sampling_unit_sha256", "post_id"):
        if len({row[field] for row in validated_contexts}) != len(validated_contexts):
            raise P0ActualAContextContractError(f"A {field} must be unique")
    if len({row["sampling_frame_sha256"] for row in validated_contexts}) != 1:
        raise P0ActualAContextContractError(
            "A context bundle must use one precommitted sampling frame"
        )
    _validate_event_chains(validated_events)
    context_by_id = {row["context_id"]: row for row in validated_contexts}
    targeted_events: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in validated_events:
        if event["target_id"] not in context_by_id:
            raise P0ActualAContextContractError("orphan A annotation event")
        targeted_events[event["target_id"]].append(event)
    referenced_claims: set[str] = set()
    for context in validated_contexts:
        claim_ids = context["source_claim_ids"]
        if any(claim_id not in by_claim for claim_id in claim_ids):
            raise P0ActualAContextContractError("A context references a missing claim")
        claim_rows = [by_claim[claim_id] for claim_id in claim_ids]
        referenced_claims.update(claim_ids)
        if source_claim_set_sha256(claim_rows) != context["source_claim_set_sha256"]:
            raise P0ActualAContextContractError("A context source claim set mismatch")
        if (
            len({row["registry_record_id"] for row in claim_rows}) != 1
            or len({row["snapshot_id"] for row in claim_rows}) != 1
        ):
            raise P0ActualAContextContractError(
                "A context claims must share one registry record and snapshot"
            )
        if any(
            row["span_end"] > len(context["content_text"])
            or context["content_text"][row["span_start"] : row["span_end"]]
            != row["span_text"]
            or not (
                row["span_start"]
                <= context["surface_start"]
                < context["surface_end"]
                <= row["span_end"]
            )
            or row["surface_text"] != context["surface_text"]
            for row in claim_rows
        ):
            raise P0ActualAContextContractError(
                "A context/source claim span and surface binding mismatch"
            )
        if any(
            row["normalized_surface"] != context["normalized_surface"]
            for row in claim_rows
        ):
            raise P0ActualAContextContractError(
                "A context/source normalized surface binding mismatch"
            )
        if context["truth_kind"] == "WORK_ID" and not any(
            row["claim_kind"] == "WORK_ALIAS"
            and row["target_work_id"] == context["truth_work_id"]
            for row in claim_rows
        ):
            raise P0ActualAContextContractError("WORK_ID lacks matching Track-A claim")
        context_events = targeted_events.get(context["context_id"], [])
        if not context_events or len({row["journal_id"] for row in context_events}) != 1:
            raise P0ActualAContextContractError("A context requires one bound review journal")
        latest = max(context_events, key=lambda item: item["journal_sequence"])
        if _timestamp(latest["occurred_at"], "occurred_at") < _timestamp(
            context["context_observed_at"], "context_observed_at"
        ):
            raise P0ActualAContextContractError(
                "latest A review must not precede context observation"
            )
        if (
            context["latest_annotation_event_id"] != latest["event_id"]
            or context["latest_annotation_event_sha256"] != latest["event_sha256"]
            or context["annotation_subject_sha256"] != latest["target_subject_sha256"]
            or context["reviewer_principal_sha256"]
            != latest["reviewer_principal_sha256"]
            or context["reviewer_assignment_receipt_sha256"]
            != latest["reviewer_assignment_receipt_sha256"]
            or context["guideline_path"] != latest["guideline_path"]
            or context["guideline_version"] != latest["guideline_version"]
            or context["guideline_sha256"] != latest["guideline_sha256"]
            or context["source_claim_ids"] != latest["evidence_claim_ids"]
            or context["evidence_cutoff"] != latest["evidence_cutoff"]
            or context["annotation_status"] != latest["annotation_status"]
            or context["truth_kind"] != latest["decision_kind"]
            or context["truth_work_id"] != latest["decision_work_id"]
            or context["truth_nil_reason"] != latest["decision_nil_reason"]
            or context["truth_reason_codes"] != latest["truth_reason_codes"]
            or context["annotation_reason_codes"]
            != latest["annotation_reason_codes"]
            or decision_payload_sha256(context) != latest["decision_payload_sha256"]
        ):
            raise P0ActualAContextContractError("latest human A event binding mismatch")
        for event in context_events:
            if _timestamp(event["occurred_at"], "occurred_at") < _timestamp(
                context["context_observed_at"], "context_observed_at"
            ):
                raise P0ActualAContextContractError(
                    "A review event must not precede context observation"
                )
            if event["target_subject_sha256"] != context["annotation_subject_sha256"]:
                raise P0ActualAContextContractError("A event subject drift")
            if (
                event["evidence_claim_ids"] != claim_ids
                or event["evidence_cutoff"] != context["evidence_cutoff"]
            ):
                raise P0ActualAContextContractError("A event evidence claim/cutoff drift")
        primary = min(context_events, key=lambda item: item["journal_sequence"])
        if any(
            (
                event["reviewer_principal_sha256"]
                != primary["reviewer_principal_sha256"]
                or event["reviewer_pseudonym_sha256"]
                != primary["reviewer_pseudonym_sha256"]
                or event["reviewer_assignment_receipt_sha256"]
                != primary["reviewer_assignment_receipt_sha256"]
            )
            for event in context_events
        ):
            raise P0ActualAContextContractError(
                "intra-rater A journal reviewer/assignment drift"
            )
    if referenced_claims != set(by_claim):
        raise P0ActualAContextContractError("unreferenced Track-A source claim")

    material = {
        "schema_version": A_CONTEXT_RECEIPT_SCHEMA,
        "record_origin": expected_origin,
        "structural_validation_verified": True,
        "validated_source_claim_count": len(claims),
        "validated_a_context_count": len(validated_contexts),
        "validated_a_annotation_event_count": len(validated_events),
        "actual_a_context_review_count": 0,
        "owner_key_verified": False,
        "reviewer_assignment_authority_verified": False,
        "guideline_authority_verified": False,
        "external_append_only_anchor_verified": False,
        "authority": "SHADOW_ONLY",
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
        "blockers": [
            "ACTUAL_A_CONTEXT_REVIEWS_0_OF_20",
            "EXTERNAL_APPEND_ONLY_ANCHOR_NOT_VERIFIED",
            "GUIDELINE_AUTHORITY_NOT_VERIFIED",
            "OWNER_KEY_NOT_VERIFIED",
            "REVIEWER_ASSIGNMENT_AUTHORITY_NOT_VERIFIED",
        ],
        "source_claim_set_sha256": source_claim_set_sha256(claims),
        "a_context_set_sha256": canonical_sha256(
            [row["row_sha256"] for row in sorted(validated_contexts, key=lambda item: item["context_id"])]
        ),
        "a_event_set_sha256": canonical_sha256(
            [row["event_sha256"] for row in sorted(validated_events, key=lambda item: item["event_id"])]
        ),
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def validate_actual_a_context_bundle(
    source_claims: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """actual-origin bundle을 검증하며 key-less 결과에 actual credit을 주지 않는다."""
    return _validate_bundle(source_claims, contexts, events, expected_origin=ACTUAL_ORIGIN)


def validate_example_a_context_bundle(
    source_claims: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """deterministic example bundle을 actual 관측 증거와 분리 검증한다."""
    return _validate_bundle(source_claims, contexts, events, expected_origin=EXAMPLE_ORIGIN)
