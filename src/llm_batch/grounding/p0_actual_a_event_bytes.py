"""A-context 전용 annotation event의 byte-exact 구조 검증기.

registry/B-event journal과 A-review journal은 schema와 의미가 다르므로 이
모듈은 ``p0_actual_authority_event_bytes``를 재사용하지 않는다. 입력 네
artifact의 canonical UTF-8 JSON/JSONL bytes, A-event hash chain, context의
latest-event projection, source claim 집합과 pre-label subject seal을 한 번에
재계산한다. 이 receipt는 파일 handle, durable predecessor, owner/runtime
authority를 증명하지 않으며 actual 20건 credit이나 P0 exit을 열지 않는다.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from . import p0_actual_a_context_contract as a_contract
from .p0_actual_registry_contract import ACTUAL_ORIGIN, EXAMPLE_ORIGIN, OPERATIONAL_EFFECT


A_EVENT_BYTES_RECEIPT_SCHEMA = "p0_actual_a_event_bytes_receipt_v1"
A_SUBJECT_SELECTION_SEAL_SCHEMA = "p0_actual_a_subject_selection_seal_v1"
EXPECTED_A_CONTEXT_COUNT = 20
MINIMUM_A_EVENT_COUNT = 20

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SUBJECT_PROJECTION_FIELDS = frozenset(
    {
        "context_id",
        "sampling_unit_sha256",
        "annotation_subject_sha256",
        "source_claim_ids",
        "source_claim_set_sha256",
    }
)
_SUBJECT_SEAL_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "seal_id",
        "claim_selection_seal_sha256",
        "sampling_frame_sha256",
        "selected_subject_count",
        "selected_subjects",
        "selected_subjects_sha256",
        "labels_observed",
        "sealed_at",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


class P0ActualAEventBytesError(ValueError):
    """A-event byte bundle이 fail-closed로 거부될 때 발생한다."""


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


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualAEventBytesError(f"{field} must be lowercase sha256")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value or value != value.strip():
        raise P0ActualAEventBytesError(f"{field} must be canonical RFC3339 text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0ActualAEventBytesError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0ActualAEventBytesError(f"{field} must include timezone")
    return parsed


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise P0ActualAEventBytesError(f"duplicate JSON key is forbidden: {key}")
        value[key] = item
    return value


def _reject_nonfinite_constant(token: str) -> None:
    raise P0ActualAEventBytesError(f"non-finite JSON constant is forbidden: {token}")


def _parse_json(raw: bytes, label: str) -> dict[str, Any]:
    if not raw:
        raise P0ActualAEventBytesError(f"{label} must not be empty")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0ActualAEventBytesError(f"{label} must not contain UTF-8 BOM")
    if b"\r" in raw:
        raise P0ActualAEventBytesError(f"{label} must use LF framing")
    if not raw.endswith(b"\n"):
        raise P0ActualAEventBytesError(f"{label} requires final LF")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0ActualAEventBytesError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise P0ActualAEventBytesError(f"{label} must be a JSON object")
    if raw != canonical_bytes(value) + b"\n":
        raise P0ActualAEventBytesError(f"{label} is not canonical JSON")
    return value


def _parse_jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if not raw:
        raise P0ActualAEventBytesError(f"{label} must not be empty")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0ActualAEventBytesError(f"{label} must not contain UTF-8 BOM")
    if b"\r" in raw:
        raise P0ActualAEventBytesError(f"{label} must use LF framing")
    if not raw.endswith(b"\n"):
        raise P0ActualAEventBytesError(f"{label} requires final LF")
    lines = raw[:-1].split(b"\n")
    if any(not line for line in lines):
        raise P0ActualAEventBytesError(f"{label} must not contain blank rows")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        try:
            value = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=_duplicate_rejecting_object,
                parse_constant=_reject_nonfinite_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P0ActualAEventBytesError(
                f"{label} row {index} is not strict UTF-8 JSON"
            ) from exc
        if not isinstance(value, dict):
            raise P0ActualAEventBytesError(f"{label} row {index} must be an object")
        if line != canonical_bytes(value):
            raise P0ActualAEventBytesError(
                f"{label} row {index} is not canonical JSON"
            )
        rows.append(value)
    return rows


def _subject_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "context_id": context["context_id"],
        "sampling_unit_sha256": context["sampling_unit_sha256"],
        "annotation_subject_sha256": context["annotation_subject_sha256"],
        "source_claim_ids": context["source_claim_ids"],
        "source_claim_set_sha256": context["source_claim_set_sha256"],
    }


def _validate_subject_seal(
    value: Any,
    contexts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _SUBJECT_SEAL_FIELDS:
        raise P0ActualAEventBytesError("A subject selection seal fields mismatch")
    row = dict(value)
    if row["schema_version"] != A_SUBJECT_SELECTION_SEAL_SCHEMA:
        raise P0ActualAEventBytesError("A subject selection seal schema mismatch")
    if row["record_origin"] != expected_origin:
        raise P0ActualAEventBytesError("A subject selection seal origin mismatch")
    if not isinstance(row["seal_id"], str) or _SAFE_ID.fullmatch(row["seal_id"]) is None:
        raise P0ActualAEventBytesError("A subject selection seal_id is invalid")
    _sha(row["claim_selection_seal_sha256"], "claim_selection_seal_sha256")
    sampling_frame = _sha(row["sampling_frame_sha256"], "sampling_frame_sha256")
    if {context["sampling_frame_sha256"] for context in contexts} != {sampling_frame}:
        raise P0ActualAEventBytesError("A subject seal sampling frame mismatch")

    selected = [
        _subject_projection(context)
        for context in sorted(contexts, key=lambda item: item["context_id"])
    ]
    for projection in selected:
        if set(projection) != _SUBJECT_PROJECTION_FIELDS:
            raise P0ActualAEventBytesError("A subject projection fields mismatch")
        claim_ids = projection["source_claim_ids"]
        if (
            not isinstance(claim_ids, list)
            or not claim_ids
            or claim_ids != sorted(set(claim_ids))
        ):
            raise P0ActualAEventBytesError("A subject claim ids must be sorted and unique")
    if len({item["sampling_unit_sha256"] for item in selected}) != len(selected):
        raise P0ActualAEventBytesError("A subject sampling units must be unique")
    if len({item["annotation_subject_sha256"] for item in selected}) != len(selected):
        raise P0ActualAEventBytesError("A annotation subjects must be unique")
    if (
        row["selected_subject_count"] != EXPECTED_A_CONTEXT_COUNT
        or row["selected_subjects"] != selected
        or _sha(row["selected_subjects_sha256"], "selected_subjects_sha256")
        != canonical_sha256(selected)
    ):
        raise P0ActualAEventBytesError("A selected subject projection mismatch")
    if row["labels_observed"] is not False:
        raise P0ActualAEventBytesError("A subject selection seal must be label blind")
    sealed = _timestamp(row["sealed_at"], "sealed_at")
    if any(
        sealed < _timestamp(context["context_observed_at"], "context_observed_at")
        for context in contexts
    ):
        raise P0ActualAEventBytesError("A subject seal predates context observation")
    if any(
        _timestamp(event["occurred_at"], "occurred_at") <= sealed
        for event in events
    ):
        raise P0ActualAEventBytesError("A event must strictly follow subject seal")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAEventBytesError("A subject seal must remain no-write")
    material = {key: item for key, item in row.items() if key != "artifact_sha256"}
    if _sha(row["artifact_sha256"], "artifact_sha256") != canonical_sha256(material):
        raise P0ActualAEventBytesError("A subject selection seal self hash mismatch")
    return row


def _require_canonical_row_order(
    claims: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> None:
    if list(claims) != sorted(claims, key=lambda item: item["claim_id"]):
        raise P0ActualAEventBytesError("source claim JSONL row order is not canonical")
    if list(contexts) != sorted(contexts, key=lambda item: item["context_id"]):
        raise P0ActualAEventBytesError("A context JSONL row order is not canonical")
    if list(events) != sorted(
        events, key=lambda item: (item["journal_id"], item["journal_sequence"])
    ):
        raise P0ActualAEventBytesError("A event JSONL row order is not canonical")


def _head_projection(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for event in events:
        current = latest.get(event["target_id"])
        if current is None or event["journal_sequence"] > current["journal_sequence"]:
            latest[event["target_id"]] = event
    return [
        {
            "context_id": event["target_id"],
            "annotation_subject_sha256": event["target_subject_sha256"],
            "journal_id": event["journal_id"],
            "head_sequence": event["journal_sequence"],
            "head_event_id": event["event_id"],
            "head_event_sha256": event["event_sha256"],
        }
        for _, event in sorted(latest.items())
    ]


def verify_a_event_bytes(
    *,
    source_claim_bytes: bytes,
    a_context_bytes: bytes,
    a_event_bytes: bytes,
    a_subject_selection_seal_bytes: bytes,
    expected_origin: str,
) -> dict[str, Any]:
    """A journal의 네 canonical byte artifact를 검증하되 authority를 주지 않는다."""

    if expected_origin not in {ACTUAL_ORIGIN, EXAMPLE_ORIGIN}:
        raise P0ActualAEventBytesError("unsupported record origin")
    claims = _parse_jsonl(source_claim_bytes, "source claim JSONL")
    contexts = _parse_jsonl(a_context_bytes, "A context JSONL")
    events = _parse_jsonl(a_event_bytes, "A event JSONL")
    seal_value = _parse_json(
        a_subject_selection_seal_bytes, "A subject selection seal"
    )
    _require_canonical_row_order(claims, contexts, events)
    if len(contexts) != EXPECTED_A_CONTEXT_COUNT or len(events) < MINIMUM_A_EVENT_COUNT:
        raise P0ActualAEventBytesError(
            "A event byte bundle requires exactly 20 contexts and at least 20 events"
        )

    validate_bundle = (
        a_contract.validate_actual_a_context_bundle
        if expected_origin == ACTUAL_ORIGIN
        else a_contract.validate_example_a_context_bundle
    )
    try:
        context_receipt = validate_bundle(claims, contexts, events)
    except a_contract.P0ActualAContextContractError as exc:
        raise P0ActualAEventBytesError(f"A context/event bundle invalid: {exc}") from exc
    seal = _validate_subject_seal(
        seal_value,
        contexts,
        events,
        expected_origin=expected_origin,
    )
    heads = _head_projection(events)
    if len(heads) != EXPECTED_A_CONTEXT_COUNT:
        raise P0ActualAEventBytesError("A head projection must cover exactly 20 contexts")
    context_by_id = {context["context_id"]: context for context in contexts}
    for head in heads:
        context = context_by_id.get(head["context_id"])
        if context is None or (
            context["annotation_subject_sha256"] != head["annotation_subject_sha256"]
            or context["latest_annotation_event_id"] != head["head_event_id"]
            or context["latest_annotation_event_sha256"] != head["head_event_sha256"]
        ):
            raise P0ActualAEventBytesError("A latest-event head projection mismatch")

    material = {
        "schema_version": A_EVENT_BYTES_RECEIPT_SCHEMA,
        "record_origin": expected_origin,
        "source_claim_file_sha256": hashlib.sha256(source_claim_bytes).hexdigest(),
        "source_claim_row_count": len(claims),
        "a_context_file_sha256": hashlib.sha256(a_context_bytes).hexdigest(),
        "a_context_row_count": len(contexts),
        "a_event_file_sha256": hashlib.sha256(a_event_bytes).hexdigest(),
        "a_event_row_count": len(events),
        "a_subject_selection_seal_file_sha256": hashlib.sha256(
            a_subject_selection_seal_bytes
        ).hexdigest(),
        "a_subject_selection_seal_row_count": 1,
        "a_subject_selection_seal_sha256": seal["artifact_sha256"],
        "a_context_receipt": context_receipt,
        "a_context_receipt_sha256": context_receipt["receipt_sha256"],
        "head_count": len(heads),
        "head_projection_sha256": canonical_sha256(heads),
        "canonical_input_bytes_verified": True,
        "a_event_hash_chains_verified": True,
        "latest_event_projection_verified": True,
        "a_subject_selection_seal_verified": True,
        "filesystem_handle_trust_verified": False,
        "durable_predecessor_verified": False,
        "annotation_append_only_verified": False,
        "owner_authority_verified": False,
        "runtime_noninterference_verified": False,
        "credited_actual_a_context_review_count": 0,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": "NO_GO_ACTUAL_A_EVENT_BYTES_STRUCTURE_ONLY",
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "A_EVENT_BYTES_RECEIPT_SCHEMA",
    "P0ActualAEventBytesError",
    "verify_a_event_bytes",
]
