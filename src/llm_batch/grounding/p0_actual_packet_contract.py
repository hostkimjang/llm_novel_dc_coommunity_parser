"""Key-less actual-P0 pilot packet의 terminal, no-write 계약.

이 모듈은 고정된 child artifact 집합을 canonical JSON/JSONL 바이트로 다시
검증하고 route/A-context receipt를 원자료에서 재계산한다. caller가 pin한
manifest file SHA-256도 반드시 일치해야 한다. 다만 portable path/stat 검사는
Windows handle-level final-path/volume/file-id/TOCTOU 증명이 아니므로, 성공한
packet도 actual 40+20 credit이나 production/full-scan 권한을 얻지 않는다.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from llm_batch.grounding import p0_actual_a_context_contract as a_contract
from llm_batch.grounding import p0_actual_authority_contract as authority_contract
from llm_batch.grounding import p0_actual_registry_contract as registry_contract
from llm_batch.grounding import p0_actual_route_contract as route_contract


PACKET_MANIFEST_SCHEMA = "p0_actual_keyless_pilot_manifest_v1"
PACKET_RECEIPT_SCHEMA = "p0_actual_keyless_pilot_packet_receipt_v2"
A_SUBJECT_SELECTION_SEAL_SCHEMA = "p0_actual_a_subject_selection_seal_v1"
CONTROLLED_PAYLOAD_ROW_SCHEMA = "p0_actual_controlled_payload_row_v1"
CANDIDATE_REGISTRY_SCHEMA = "p0_actual_a_candidate_registry_v1"
PACKET_MANIFEST_FILENAME = "p0_actual_keyless_pilot_manifest_v1.json"

ACTUAL_ORIGIN = registry_contract.ACTUAL_ORIGIN
EXAMPLE_ORIGIN = registry_contract.EXAMPLE_ORIGIN
OPERATIONAL_EFFECT = registry_contract.OPERATIONAL_EFFECT

EXPECTED_INPUT_COUNT = 40
EXPECTED_A_CONTEXT_COUNT = 20

CHILD_FILES = (
    ("source_snapshots", "source_snapshots.jsonl", "application/x-ndjson"),
    (
        "controlled_payloads",
        "controlled_payloads.jsonl",
        "application/x-ndjson",
    ),
    ("source_input_plan", "source_input_plan.json", "application/json"),
    (
        "label_blind_selection_seal",
        "label_blind_selection_seal.json",
        "application/json",
    ),
    ("source_claims", "source_claims.jsonl", "application/x-ndjson"),
    ("terminal_queue", "terminal_queue.jsonl", "application/x-ndjson"),
    ("parser_receipt", "parser_receipt.json", "application/json"),
    ("candidate_registry", "candidate_registry.json", "application/json"),
    ("a_contexts", "a_contexts.jsonl", "application/x-ndjson"),
    (
        "a_subject_selection_seal",
        "a_subject_selection_seal.json",
        "application/json",
    ),
    (
        "a_annotation_events",
        "a_annotation_events.jsonl",
        "application/x-ndjson",
    ),
    ("route_receipt", "route_receipt.json", "application/json"),
    ("a_context_receipt", "a_context_receipt.json", "application/json"),
)

BLOCKERS = (
    "ACTUAL_A_CONTEXT_REVIEWS_CREDITED_0_OF_20",
    "ACTUAL_AUTHORITY_JOURNAL_WATCH_BUNDLE_NOT_BOUND",
    "ACTUAL_LAUNCH_CAPTURE_BINDING_NOT_VERIFIED",
    "ACTUAL_OS_WRITE_DENY_WITNESS_NOT_VERIFIED",
    "ACTUAL_OWNER_EXTERNAL_TRUST_NOT_VERIFIED",
    "ACTUAL_RUNTIME_NONINTERFERENCE_NOT_VERIFIED",
    "ACTUAL_SOURCE_CLAIMS_CREDITED_0_OF_40",
    "FILESYSTEM_HANDLE_TRUST_NOT_VERIFIED",
    "KEYLESS_PACKET_NO_ACTUAL_AUTHORITY",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")

_FILE_REF_FIELDS = frozenset({"role", "path", "media_type", "rows", "bytes", "sha256"})
_PROFILE_COUNT_FIELDS = frozenset(route_contract.SOURCE_PROFILES)
_ROUTE_COUNT_FIELDS = frozenset(
    {
        "input_count",
        "typed_input_count",
        "claim_row_count",
        "generic_count",
        "error_count",
    }
)
_A_STATUS_COUNT_FIELDS = frozenset(a_contract.ANNOTATION_STATUSES)
_OBSERVED_COUNT_FIELDS = frozenset(
    {
        "source_snapshot_count",
        "source_claim_row_count",
        "selected_source_claim_count",
        "terminal_queue_count",
        "a_context_review_count",
        "a_annotation_event_count",
    }
)
_CREDITED_COUNT_FIELDS = frozenset(
    {"actual_source_claim_count", "actual_a_context_review_count"}
)
_A_SUBJECT_PROJECTION_FIELDS = frozenset(
    {
        "context_id",
        "sampling_unit_sha256",
        "annotation_subject_sha256",
        "source_claim_ids",
        "source_claim_set_sha256",
    }
)
_A_SUBJECT_SEAL_FIELDS = frozenset(
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
_CONTROLLED_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "registry_record_id",
        "payload_ref",
        "content_text",
        "content_bytes",
        "content_sha256",
        "normalized_text_sha256",
        "row_sha256",
    }
)
_CANDIDATE_REGISTRY_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "registry_id",
        "created_at",
        "enumeration_status",
        "work_ids",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "packet_id",
        "created_at",
        "files",
        "source_profile_counts",
        "route_counts",
        "a_annotation_status_counts",
        "observed_counts",
        "credited_counts",
        "route_receipt_sha256",
        "parser_receipt_sha256",
        "a_context_receipt_sha256",
        "a_subject_selection_seal_sha256",
        "a_selected_subject_count",
        "a_selected_subjects_sha256",
        "filesystem_handle_trust_verified",
        "authority_journal_watch_bundle_verified",
        "external_owner_authority_verified",
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
        "operational_effect",
        "gate_status",
        "blockers",
        "artifact_sha256",
    }
)


class P0ActualPacketError(ValueError):
    """Key-less terminal packet이 fail-closed로 거부될 때 발생한다."""


def canonical_bytes(value: Any) -> bytes:
    """JSON 값의 canonical UTF-8 표현을 반환한다."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def json_file_bytes(value: Any) -> bytes:
    """단일 JSON artifact의 유일하게 허용되는 바이트 표현."""

    return canonical_bytes(value) + b"\n"


def jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    """JSONL artifact의 유일하게 허용되는 바이트 표현."""

    return b"".join(canonical_bytes(row) + b"\n" for row in rows)


def with_manifest_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    """manifest 내부 self-hash를 계산한다(외부 file SHA와는 별개)."""

    material = dict(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": canonical_sha256(material)}


def with_packet_receipt_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    """packet receipt의 파생 projection 전체를 self-hash한다."""

    material = dict(value)
    material.pop("receipt_sha256", None)
    return {**material, "receipt_sha256": canonical_sha256(material)}


def file_ref(
    role: str, path: str, media_type: str, raw: bytes, rows: int
) -> dict[str, Any]:
    """테스트/생성기에서 사용할 strict child file reference를 만든다."""

    return {
        "role": role,
        "path": path,
        "media_type": media_type,
        "rows": rows,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _strict(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualPacketError(f"{label} must be an object")
    if set(value) != fields:
        raise P0ActualPacketError(
            f"{label} fields mismatch: missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise P0ActualPacketError(f"{field} must be canonical non-empty text")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if _SAFE_ID.fullmatch(text) is None:
        raise P0ActualPacketError(f"{field} must be a safe identifier")
    return text


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualPacketError(f"{field} must be lowercase sha256")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P0ActualPacketError(f"{field} must be a nonnegative integer")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0ActualPacketError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0ActualPacketError(f"{field} must include timezone")
    return parsed


def _count_object(value: Any, fields: frozenset[str], label: str) -> dict[str, int]:
    row = _strict(value, fields, label)
    return {field: _nonnegative_int(row[field], f"{label}.{field}") for field in fields}


def _reject_constant(value: str) -> None:
    raise P0ActualPacketError(f"non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise P0ActualPacketError(f"duplicate JSON key is forbidden: {key}")
        value[key] = item
    return value


def _parse_json(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0ActualPacketError(f"{label} is not strict UTF-8 JSON") from exc
    if raw != json_file_bytes(value):
        raise P0ActualPacketError(f"{label} bytes are not canonical JSON with final LF")
    return value


def _parse_jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if not raw or not raw.endswith(b"\n") or b"\r" in raw:
        raise P0ActualPacketError(f"{label} must be non-empty LF-terminated JSONL")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw[:-1].split(b"\n"), start=1):
        if not line:
            raise P0ActualPacketError(f"{label} contains a blank row")
        try:
            value = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P0ActualPacketError(f"{label} row {index} is invalid JSON") from exc
        if not isinstance(value, dict):
            raise P0ActualPacketError(f"{label} row {index} must be an object")
        rows.append(value)
    if raw != jsonl_bytes(rows):
        raise P0ActualPacketError(f"{label} bytes are not canonical JSONL")
    return rows


def _self_hash(row: Mapping[str, Any], field: str, label: str) -> None:
    stored = _sha(row[field], field)
    material = {key: item for key, item in row.items() if key != field}
    if stored != canonical_sha256(material):
        raise P0ActualPacketError(f"{label} self hash mismatch")


def _sorted_unique_texts(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise P0ActualPacketError(f"{field} must be a list")
    rows = [_text(item, field) for item in value]
    if rows != sorted(set(rows)):
        raise P0ActualPacketError(f"{field} must be sorted and unique")
    return rows


def _validate_controlled_payloads(
    values: Sequence[Mapping[str, Any]],
    snapshots: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str,
) -> dict[str, str]:
    if not isinstance(values, list):
        raise P0ActualPacketError("controlled payloads must be JSONL rows")
    by_registry: dict[str, str] = {}
    for value in values:
        row = _strict(value, _CONTROLLED_PAYLOAD_FIELDS, "controlled payload row")
        if row["schema_version"] != CONTROLLED_PAYLOAD_ROW_SCHEMA:
            raise P0ActualPacketError("controlled payload row schema mismatch")
        if row["record_origin"] != expected_origin:
            raise P0ActualPacketError("controlled payload origin mismatch")
        registry_id = _identifier(row["registry_record_id"], "registry_record_id")
        payload_ref = _text(row["payload_ref"], "payload_ref")
        if Path(payload_ref).name != payload_ref or ".." in Path(payload_ref).parts:
            raise P0ActualPacketError("controlled payload_ref must be a fixed basename")
        content = row["content_text"]
        if not isinstance(content, str):
            raise P0ActualPacketError("controlled payload content_text must be text")
        raw = content.encode("utf-8")
        if row["content_bytes"] != len(raw):
            raise P0ActualPacketError("controlled payload byte count mismatch")
        digest = hashlib.sha256(raw).hexdigest()
        if _sha(row["content_sha256"], "content_sha256") != digest:
            raise P0ActualPacketError("controlled payload content hash mismatch")
        if _sha(row["normalized_text_sha256"], "normalized_text_sha256") != digest:
            raise P0ActualPacketError("identity-normalized payload hash mismatch")
        _self_hash(row, "row_sha256", "controlled payload row")
        if registry_id in by_registry:
            raise P0ActualPacketError("controlled payload registry id must be unique")
        by_registry[registry_id] = content
    source_by_id = {row["registry_record_id"]: row for row in snapshots}
    if set(by_registry) != set(source_by_id):
        raise P0ActualPacketError("controlled payload inventory must cover every snapshot")
    seen_refs: set[str] = set()
    for value in values:
        source = source_by_id[value["registry_record_id"]]
        content = by_registry[value["registry_record_id"]]
        raw = content.encode("utf-8")
        if (
            value["payload_ref"] != source["payload_ref"]
            or value["payload_ref"] in seen_refs
            or source["retention_class"] != "CONTROLLED_RAW"
            or source["normalization_version"] != "utf8_identity_v1"
            or source["response_bytes"] != len(raw)
            or source["response_sha256"] != hashlib.sha256(raw).hexdigest()
            or source["normalized_text_sha256"] != hashlib.sha256(raw).hexdigest()
        ):
            raise P0ActualPacketError("controlled payload/snapshot binding mismatch")
        seen_refs.add(value["payload_ref"])
    return by_registry


def validate_claim_payload_spans(
    claims: Sequence[Mapping[str, Any]],
    payload_text_by_registry: Mapping[str, str],
) -> None:
    """캡처 원문에서 모든 claim exact span을 다시 재생한다."""

    for claim in claims:
        payload = payload_text_by_registry.get(claim["registry_record_id"])
        if payload is None or (
            isinstance(claim["span_start"], bool)
            or not isinstance(claim["span_start"], int)
            or isinstance(claim["span_end"], bool)
            or not isinstance(claim["span_end"], int)
            or claim["span_start"] < 0
            or claim["span_end"] > len(payload)
            or payload[claim["span_start"] : claim["span_end"]]
            != claim["span_text"]
        ):
            raise P0ActualPacketError("source claim span does not match captured payload")


def _validate_candidate_registry(value: Any, expected_origin: str) -> dict[str, Any]:
    row = dict(_strict(value, _CANDIDATE_REGISTRY_FIELDS, "candidate registry"))
    if row["schema_version"] != CANDIDATE_REGISTRY_SCHEMA:
        raise P0ActualPacketError("candidate registry schema mismatch")
    if row["record_origin"] != expected_origin:
        raise P0ActualPacketError("candidate registry origin mismatch")
    _identifier(row["registry_id"], "registry_id")
    _timestamp(row["created_at"], "created_at")
    if row["enumeration_status"] != "COMPLETE":
        raise P0ActualPacketError("terminal candidate registry must be COMPLETE")
    _sorted_unique_texts(row["work_ids"], "work_ids", allow_empty=True)
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualPacketError("candidate registry must remain no-write")
    _self_hash(row, "artifact_sha256", "candidate registry")
    return row


def a_subject_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "context_id": context["context_id"],
        "sampling_unit_sha256": context["sampling_unit_sha256"],
        "annotation_subject_sha256": context["annotation_subject_sha256"],
        "source_claim_ids": context["source_claim_ids"],
        "source_claim_set_sha256": context["source_claim_set_sha256"],
    }


def with_a_subject_seal_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": canonical_sha256(material)}


def validate_a_subject_selection_seal(
    value: Any,
    contexts: Sequence[Mapping[str, Any]],
    *,
    claim_selection_seal: Mapping[str, Any],
    expected_origin: str,
) -> dict[str, Any]:
    row = dict(_strict(value, _A_SUBJECT_SEAL_FIELDS, "A subject selection seal"))
    if row["schema_version"] != A_SUBJECT_SELECTION_SEAL_SCHEMA:
        raise P0ActualPacketError("A subject selection seal schema mismatch")
    if row["record_origin"] != expected_origin:
        raise P0ActualPacketError("A subject selection seal origin mismatch")
    _identifier(row["seal_id"], "seal_id")
    if _sha(
        row["claim_selection_seal_sha256"], "claim_selection_seal_sha256"
    ) != claim_selection_seal["artifact_sha256"]:
        raise P0ActualPacketError("A subject seal/claim seal binding mismatch")
    if len(contexts) != EXPECTED_A_CONTEXT_COUNT:
        raise P0ActualPacketError("A subject seal requires exactly 20 contexts")
    frame_hashes = {context["sampling_frame_sha256"] for context in contexts}
    if len(frame_hashes) != 1 or _sha(
        row["sampling_frame_sha256"], "sampling_frame_sha256"
    ) not in frame_hashes:
        raise P0ActualPacketError("A subject seal sampling frame mismatch")
    selected = [
        a_subject_projection(context)
        for context in sorted(contexts, key=lambda item: item["context_id"])
    ]
    for projection in selected:
        _strict(projection, _A_SUBJECT_PROJECTION_FIELDS, "A subject projection")
        _sorted_unique_texts(projection["source_claim_ids"], "source_claim_ids")
    if len({item["sampling_unit_sha256"] for item in selected}) != len(selected):
        raise P0ActualPacketError("A subject semantic sampling units must be unique")
    if len({item["annotation_subject_sha256"] for item in selected}) != len(selected):
        raise P0ActualPacketError("A annotation subjects must be unique")
    if row["selected_subject_count"] != len(selected) or row["selected_subjects"] != selected:
        raise P0ActualPacketError("A selected subjects do not match pre-label projections")
    if _sha(
        row["selected_subjects_sha256"], "selected_subjects_sha256"
    ) != canonical_sha256(selected):
        raise P0ActualPacketError("A selected subject set binding mismatch")
    if row["labels_observed"] is not False:
        raise P0ActualPacketError("A subject selection must be label blind")
    sealed = _timestamp(row["sealed_at"], "sealed_at")
    if sealed < _timestamp(claim_selection_seal["sealed_at"], "sealed_at"):
        raise P0ActualPacketError("A subject seal cannot predate claim selection seal")
    if any(
        sealed < _timestamp(context["context_observed_at"], "context_observed_at")
        for context in contexts
    ):
        raise P0ActualPacketError(
            "A subject seal cannot predate any context observation"
        )
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualPacketError("A subject selection seal must remain no-write")
    _self_hash(row, "artifact_sha256", "A subject selection seal")
    return row


def _validate_manifest(value: Any, expected_origin: str) -> dict[str, Any]:
    row = dict(_strict(value, _MANIFEST_FIELDS, "packet manifest"))
    if row["schema_version"] != PACKET_MANIFEST_SCHEMA:
        raise P0ActualPacketError("packet manifest schema mismatch")
    if expected_origin not in {ACTUAL_ORIGIN, EXAMPLE_ORIGIN}:
        raise P0ActualPacketError("unsupported packet origin")
    if row["record_origin"] != expected_origin:
        raise P0ActualPacketError("actual/example packet origin mismatch")
    _identifier(row["packet_id"], "packet_id")
    _timestamp(row["created_at"], "created_at")

    if not isinstance(row["files"], list):
        raise P0ActualPacketError("manifest files must be a list")
    expected_files = list(CHILD_FILES)
    refs: list[dict[str, Any]] = []
    for index, value_ref in enumerate(row["files"]):
        ref = dict(_strict(value_ref, _FILE_REF_FIELDS, "child file reference"))
        role, path, media_type = expected_files[index] if index < len(expected_files) else (None, None, None)
        if (ref["role"], ref["path"], ref["media_type"]) != (role, path, media_type):
            raise P0ActualPacketError("child file inventory/order is not the fixed packet set")
        _nonnegative_int(ref["rows"], "rows")
        _nonnegative_int(ref["bytes"], "bytes")
        _sha(ref["sha256"], "sha256")
        refs.append(ref)
    if len(refs) != len(expected_files):
        raise P0ActualPacketError("child file inventory/order is not the fixed packet set")
    if any(ref["path"] == PACKET_MANIFEST_FILENAME for ref in refs):
        raise P0ActualPacketError("manifest must be excluded from child files")

    _count_object(row["source_profile_counts"], _PROFILE_COUNT_FIELDS, "source_profile_counts")
    _count_object(row["route_counts"], _ROUTE_COUNT_FIELDS, "route_counts")
    _count_object(
        row["a_annotation_status_counts"],
        _A_STATUS_COUNT_FIELDS,
        "a_annotation_status_counts",
    )
    _count_object(row["observed_counts"], _OBSERVED_COUNT_FIELDS, "observed_counts")
    credited = _count_object(row["credited_counts"], _CREDITED_COUNT_FIELDS, "credited_counts")
    if any(credited.values()):
        raise P0ActualPacketError("key-less packet actual credited counts must remain zero")
    _sha(row["route_receipt_sha256"], "route_receipt_sha256")
    _sha(row["parser_receipt_sha256"], "parser_receipt_sha256")
    _sha(row["a_context_receipt_sha256"], "a_context_receipt_sha256")
    _sha(
        row["a_subject_selection_seal_sha256"],
        "a_subject_selection_seal_sha256",
    )
    if row["a_selected_subject_count"] != EXPECTED_A_CONTEXT_COUNT:
        raise P0ActualPacketError("A selected subject count must be exactly 20")
    _sha(row["a_selected_subjects_sha256"], "a_selected_subjects_sha256")
    if row["filesystem_handle_trust_verified"] is not False:
        raise P0ActualPacketError("filesystem handle trust must remain unverified")
    for field in (
        "authority_journal_watch_bundle_verified",
        "external_owner_authority_verified",
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    ):
        if row[field] is not False:
            raise P0ActualPacketError(f"{field} must remain false")
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualPacketError("packet must remain shadow-only")
    if row["gate_status"] != "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED":
        raise P0ActualPacketError("key-less packet gate must remain NO_GO")
    if row["blockers"] != list(BLOCKERS):
        raise P0ActualPacketError("packet blockers must be the fixed ordered set")
    stored = _sha(row["artifact_sha256"], "artifact_sha256")
    material = {key: item for key, item in row.items() if key != "artifact_sha256"}
    if stored != canonical_sha256(material):
        raise P0ActualPacketError("packet manifest self hash mismatch")
    return row


def _expected_file_map() -> dict[str, tuple[str, str]]:
    return {path: (role, media_type) for role, path, media_type in CHILD_FILES}


def validate_packet_bytes(
    manifest_bytes: bytes,
    child_files: Mapping[str, bytes],
    *,
    expected_manifest_sha256: str,
    expected_origin: str = ACTUAL_ORIGIN,
) -> dict[str, Any]:
    """메모리의 packet 바이트를 검증한다; manifest SHA pin은 필수다."""

    pinned = _sha(expected_manifest_sha256, "expected_manifest_sha256")
    actual_manifest_file_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if actual_manifest_file_sha != pinned:
        raise P0ActualPacketError("caller-pinned manifest file sha256 mismatch")
    manifest = _validate_manifest(_parse_json(manifest_bytes, "packet manifest"), expected_origin)

    expected_file_map = _expected_file_map()
    if set(child_files) != set(expected_file_map):
        raise P0ActualPacketError("supplied child file names do not match fixed inventory")
    refs = {ref["path"]: ref for ref in manifest["files"]}
    artifacts: dict[str, Any] = {}
    for path, raw in child_files.items():
        if not isinstance(raw, bytes):
            raise P0ActualPacketError(f"child file must be bytes: {path}")
        role, media_type = expected_file_map[path]
        ref = refs[path]
        if (
            ref["role"] != role
            or ref["media_type"] != media_type
            or ref["bytes"] != len(raw)
            or ref["sha256"] != hashlib.sha256(raw).hexdigest()
        ):
            raise P0ActualPacketError(f"child file reference mismatch: {path}")
        if media_type == "application/json":
            parsed = _parse_json(raw, path)
            actual_rows = 1
        else:
            parsed = _parse_jsonl(raw, path)
            actual_rows = len(parsed)
        if ref["rows"] != actual_rows:
            raise P0ActualPacketError(f"child file row count mismatch: {path}")
        artifacts[role] = parsed

    snapshots = artifacts["source_snapshots"]
    payload_text_by_registry = _validate_controlled_payloads(
        artifacts["controlled_payloads"],
        snapshots,
        expected_origin=expected_origin,
    )
    candidate_registry = _validate_candidate_registry(
        artifacts["candidate_registry"], expected_origin
    )
    authority_origin = (
        authority_contract.ACTUAL_ORIGIN
        if expected_origin == ACTUAL_ORIGIN
        else authority_contract.EXAMPLE_ORIGIN
    )
    try:
        parser_receipt = authority_contract.validate_parser_receipt(
            artifacts["parser_receipt"], authority_origin
        )
    except authority_contract.P0ActualAuthorityError as exc:
        raise P0ActualPacketError(f"parser receipt invalid: {exc}") from exc

    try:
        route_receipt = route_contract.validate_route_bundle(
            source_snapshots=snapshots,
            input_plan=artifacts["source_input_plan"],
            selection_seal=artifacts["label_blind_selection_seal"],
            source_claims=artifacts["source_claims"],
            terminal_rows=artifacts["terminal_queue"],
            parser_receipt=(
                parser_receipt if expected_origin == ACTUAL_ORIGIN else None
            ),
            expected_origin=expected_origin,
        )
    except route_contract.P0ActualRouteError as exc:
        raise P0ActualPacketError(f"route bundle invalid: {exc}") from exc
    if artifacts["route_receipt"] != route_receipt:
        raise P0ActualPacketError("stored route receipt differs from recomputation")
    if (
        route_receipt["selection_complete"] is not True
        or route_receipt["selected_claim_count"] != EXPECTED_INPUT_COUNT
        or route_receipt["error_count"] != 0
    ):
        raise P0ActualPacketError(
            "terminal route requires complete 40-claim selection and zero parser errors"
        )
    if expected_origin == ACTUAL_ORIGIN and (
        route_receipt["parser_receipt_verified"] is not True
        or route_receipt["parser_runtime_status"] != "COMPLETE"
        or route_receipt["route_accounting_packet_complete"] is not True
    ):
        raise P0ActualPacketError(
            "actual terminal route requires a complete bound parser receipt"
        )

    source_by_registry = {row["registry_record_id"]: row for row in snapshots}
    claims_by_id = {row["claim_id"]: row for row in artifacts["source_claims"]}
    if len(claims_by_id) != len(artifacts["source_claims"]):
        raise P0ActualPacketError("source claim ids must be unique")
    validate_claim_payload_spans(
        artifacts["source_claims"], payload_text_by_registry
    )

    contexts = artifacts["a_contexts"]
    selected_claim_ids = {
        row["claim_id"]
        for row in artifacts["label_blind_selection_seal"]["selected_claim_units"]
    }
    selected_subjects: list[dict[str, Any]] = []
    for context in contexts:
        source_claim_ids = context.get("source_claim_ids")
        if (
            not isinstance(source_claim_ids, list)
            or not source_claim_ids
            or source_claim_ids != sorted(set(source_claim_ids))
            or not set(source_claim_ids).issubset(selected_claim_ids)
        ):
            raise P0ActualPacketError(
                "each A selected subject must bind a nonempty sealed-claim subset"
            )
        claim_rows = [claims_by_id[claim_id] for claim_id in source_claim_ids]
        registry_ids = {claim["registry_record_id"] for claim in claim_rows}
        if len(registry_ids) != 1:
            raise P0ActualPacketError(
                "one A context must bind claims from one captured source"
            )
        source = source_by_registry[next(iter(registry_ids))]
        if (
            context["content_text"] != payload_text_by_registry[source["registry_record_id"]]
            or context["platform_scope"] != source["platform"]
            or context["community_scope"] != source["community_scope"]
        ):
            raise P0ActualPacketError("A context/captured source binding mismatch")
        if _timestamp(source["collected_at"], "collected_at") > _timestamp(
            context["evidence_cutoff"], "evidence_cutoff"
        ):
            raise P0ActualPacketError("A context uses source captured after evidence cutoff")
        if (
            context["candidate_registry_snapshot_sha256"]
            != candidate_registry["artifact_sha256"]
            or not set(context["candidate_work_ids"]).issubset(
                candidate_registry["work_ids"]
            )
        ):
            raise P0ActualPacketError("A context/candidate registry binding mismatch")
        if _timestamp(candidate_registry["created_at"], "created_at") > _timestamp(
            context["evidence_cutoff"], "evidence_cutoff"
        ):
            raise P0ActualPacketError("candidate registry postdates A evidence cutoff")
        selected_subjects.append(a_subject_projection(context))
    a_claim_ids = {
        claim_id
        for context in contexts
        for claim_id in context.get("source_claim_ids", [])
    }
    a_claims = [
        claim for claim in artifacts["source_claims"] if claim.get("claim_id") in a_claim_ids
    ]
    validate_a = (
        a_contract.validate_actual_a_context_bundle
        if expected_origin == ACTUAL_ORIGIN
        else a_contract.validate_example_a_context_bundle
    )
    try:
        a_receipt = validate_a(
            a_claims,
            artifacts["a_contexts"],
            artifacts["a_annotation_events"],
        )
    except a_contract.P0ActualAContextContractError as exc:
        raise P0ActualPacketError(f"A-context bundle invalid: {exc}") from exc
    if artifacts["a_context_receipt"] != a_receipt:
        raise P0ActualPacketError("stored A-context receipt differs from recomputation")

    a_subject_seal = validate_a_subject_selection_seal(
        artifacts["a_subject_selection_seal"],
        contexts,
        claim_selection_seal=artifacts["label_blind_selection_seal"],
        expected_origin=expected_origin,
    )

    seal_time = _timestamp(a_subject_seal["sealed_at"], "sealed_at")
    event_by_id = {
        event["event_id"]: event for event in artifacts["a_annotation_events"]
    }
    for context in contexts:
        latest = event_by_id.get(context["latest_annotation_event_id"])
        if latest is None:
            raise P0ActualPacketError("A subject latest event is missing")
    if any(
        _timestamp(event["occurred_at"], "occurred_at") <= seal_time
        for event in artifacts["a_annotation_events"]
    ):
        raise P0ActualPacketError("every A event must occur after subject selection seal")
    manifest_time = _timestamp(manifest["created_at"], "created_at")
    if manifest_time <= seal_time or any(
        _timestamp(event["occurred_at"], "occurred_at") > manifest_time
        for event in artifacts["a_annotation_events"]
    ):
        raise P0ActualPacketError(
            "terminal manifest must be finalized after seal and all A events"
        )

    sources = snapshots
    claims = artifacts["source_claims"]
    terminals = artifacts["terminal_queue"]
    events = artifacts["a_annotation_events"]
    profile_counts = {profile: 0 for profile in route_contract.SOURCE_PROFILES}
    profile_counts.update(Counter(row["source_profile"] for row in sources))
    route_counts = {
        field: route_receipt[field]
        for field in _ROUTE_COUNT_FIELDS
    }
    status_counts = {status: 0 for status in a_contract.ANNOTATION_STATUSES}
    status_counts.update(Counter(row["annotation_status"] for row in contexts))
    observed_counts = {
        "source_snapshot_count": len(sources),
        "source_claim_row_count": len(claims),
        "selected_source_claim_count": route_receipt["selected_claim_count"],
        "terminal_queue_count": len(terminals),
        "a_context_review_count": len(contexts),
        "a_annotation_event_count": len(events),
    }
    if len(sources) != EXPECTED_INPUT_COUNT:
        raise P0ActualPacketError("terminal packet requires exactly 40 observed source inputs")
    if len(contexts) != EXPECTED_A_CONTEXT_COUNT:
        raise P0ActualPacketError("terminal packet requires exactly 20 observed A-context reviews")
    expected_bindings = {
        "source_profile_counts": profile_counts,
        "route_counts": route_counts,
        "a_annotation_status_counts": status_counts,
        "observed_counts": observed_counts,
        "route_receipt_sha256": canonical_sha256(route_receipt),
        "parser_receipt_sha256": parser_receipt["artifact_sha256"],
        "a_context_receipt_sha256": canonical_sha256(a_receipt),
        "a_subject_selection_seal_sha256": a_subject_seal["artifact_sha256"],
        "a_selected_subject_count": len(selected_subjects),
        "a_selected_subjects_sha256": canonical_sha256(
            sorted(selected_subjects, key=lambda item: item["context_id"])
        ),
    }
    for field, expected in expected_bindings.items():
        if manifest[field] != expected:
            raise P0ActualPacketError(f"manifest recomputed binding mismatch: {field}")

    return with_packet_receipt_hash({
        "schema_version": PACKET_RECEIPT_SCHEMA,
        "record_origin": expected_origin,
        "packet_id": manifest["packet_id"],
        "manifest_created_at": manifest["created_at"],
        "manifest_file_sha256": actual_manifest_file_sha,
        "manifest_artifact_sha256": manifest["artifact_sha256"],
        "child_file_count": len(CHILD_FILES),
        "byte_inventory_binding_verified": True,
        "portable_directory_binding_verified": False,
        "parser_receipt_schema_verified": True,
        "route_accounting_packet_complete": route_receipt[
            "route_accounting_packet_complete"
        ],
        "authority_journal_watch_bundle_verified": False,
        "route_receipt_recomputed": True,
        "a_context_receipt_recomputed": True,
        "route_receipt_sha256": canonical_sha256(route_receipt),
        "parser_receipt_sha256": parser_receipt["artifact_sha256"],
        "a_context_receipt_sha256": canonical_sha256(a_receipt),
        "a_subject_selection_seal_sha256": a_subject_seal[
            "artifact_sha256"
        ],
        "source_input_plan_sha256": route_receipt["source_input_plan_sha256"],
        "sampling_frame_sha256": route_receipt["sampling_frame_sha256"],
        "route_parser_manifest_sha256": route_receipt[
            "parser_manifest_sha256"
        ],
        "route_parser_version": route_receipt["parser_version"],
        "route_parser_launch_sha256": route_receipt["parser_launch_sha256"],
        "route_parser_capture_manifest_sha256": route_receipt[
            "parser_capture_manifest_sha256"
        ],
        "source_profile_counts": profile_counts,
        "route_counts": route_counts,
        "a_annotation_status_counts": status_counts,
        "a_selected_subject_count": len(selected_subjects),
        "a_selected_subjects_sha256": canonical_sha256(
            sorted(selected_subjects, key=lambda item: item["context_id"])
        ),
        "observed_counts": observed_counts,
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "filesystem_handle_trust_verified": False,
        "external_owner_authority_verified": False,
        "os_write_deny_verified": False,
        "runtime_noninterference_verified": False,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
        "blockers": list(BLOCKERS),
    })


def validate_packet_directory(
    packet_dir: Path | str,
    *,
    expected_manifest_sha256: str,
    expected_origin: str = ACTUAL_ORIGIN,
) -> dict[str, Any]:
    """고정 directory inventory를 읽고 pure bytes validator로 위임한다.

    symlink/hardlink 같은 명백한 alias는 거부하지만 이 검사는 open handle에
    고정된 Windows final path/volume/file ID/USN 검증이 아니다.
    """

    root = Path(packet_dir)
    if not root.is_dir() or root.is_symlink():
        raise P0ActualPacketError("packet directory must be a real directory")
    expected_names = {PACKET_MANIFEST_FILENAME, *_expected_file_map().keys()}
    actual_names = {entry.name for entry in root.iterdir()}
    if actual_names != expected_names:
        raise P0ActualPacketError("packet directory inventory mismatch")
    raw_by_name: dict[str, bytes] = {}
    identities: dict[str, tuple[int, int, int, int]] = {}
    for name in sorted(expected_names):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise P0ActualPacketError(f"packet artifact must be a regular file: {name}")
        stat = path.stat()
        if getattr(stat, "st_nlink", 1) != 1:
            raise P0ActualPacketError(f"packet artifact hardlink is forbidden: {name}")
        identities[name] = (
            int(getattr(stat, "st_dev", 0)),
            int(getattr(stat, "st_ino", 0)),
            int(stat.st_size),
            int(stat.st_mtime_ns),
        )
        raw_by_name[name] = path.read_bytes()
        after = path.stat()
        if identities[name] != (
            int(getattr(after, "st_dev", 0)),
            int(getattr(after, "st_ino", 0)),
            int(after.st_size),
            int(after.st_mtime_ns),
        ):
            raise P0ActualPacketError(f"packet artifact changed while reading: {name}")
    if {entry.name for entry in root.iterdir()} != expected_names:
        raise P0ActualPacketError("packet directory inventory changed while reading")
    manifest_raw = raw_by_name.pop(PACKET_MANIFEST_FILENAME)
    receipt = validate_packet_bytes(
        manifest_raw,
        raw_by_name,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_origin=expected_origin,
    )
    return with_packet_receipt_hash(
        {**receipt, "portable_directory_binding_verified": True}
    )
