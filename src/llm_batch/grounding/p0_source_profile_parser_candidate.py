"""Presented exact-envelope -> claim/terminal artifact pure projector.

This module deliberately does not run a subprocess, open a path, inspect the
environment, or append a ledger.  It accepts one canonical byte request and
returns one canonical byte response for the controlled example namespace.
The separate parent validator must replay the transform before any artifact is
used by the existing route/packet contracts.

Structured inputs use a deliberately narrow exact envelope.  Only an explicit
``'<surface>'은 <definition>을 뜻한다`` sentence can become a new-sense
candidate.  A mere mention has no typed output route and becomes a bounded
parser error.  The component has no field or code path for a canonical
work/sense target, so an ambiguous surface such as ``아생갤`` cannot be
promoted to a work, a non-term judgement, or a real-world gallery here.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from llm_batch.grounding import p0_actual_registry_contract as registry_contract
from llm_batch.grounding import p0_actual_route_contract as route_contract


REQUEST_SCHEMA = "p0_source_profile_parser_candidate_request_v1"
RESPONSE_SCHEMA = "p0_source_profile_parser_candidate_response_v1"
ENVELOPE_SCHEMA = "p0_source_profile_exact_envelope_v1"
OPERATION = "SOURCE_PROFILE_TERMINAL_ARTIFACT_SHADOW_V1"
PARSER_VERSION = "source-profile-exact-envelope-projector-v1"
PRODUCER_KIND = "PURE_EXACT_ENVELOPE_PROJECTOR_COMPONENT"
OPERATIONAL_EFFECT = registry_contract.OPERATIONAL_EFFECT
GATE_STATUS = (
    "EXACT_ENVELOPE_PROJECTOR_COMPONENT_ONLY_SOURCE_PARSER_SANDBOX_NO_GO"
)

MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAYLOAD_BYTES = 256 * 1024
MAX_TOTAL_PAYLOAD_BYTES = 4 * 1024 * 1024
MAX_DOCUMENT_CHARS = 4096
MAX_ENTRIES_PER_INPUT = 64

ENTRY_EXPLICIT_DEFINITION_CANDIDATE = "EXPLICIT_DEFINITION_CANDIDATE"
ENTRY_KINDS = (ENTRY_EXPLICIT_DEFINITION_CANDIDATE,)

PARSER_MANIFEST = {
    "schema_version": "p0_source_profile_exact_envelope_projector_manifest_v1",
    "parser_version": PARSER_VERSION,
    "operation": OPERATION,
    "producer_kind": PRODUCER_KIND,
    "supported_profiles": list(route_contract.SOURCE_PROFILES),
    "structured_envelope_schema": ENVELOPE_SCHEMA,
    "structured_entry_kinds": list(ENTRY_KINDS),
    "structured_relation_grammar": "'<surface>'은 <definition>을 뜻한다",
    "semantic_target_policy": "NO_WORK_OR_SENSE_TARGET_ID_OUTPUT",
    "generic_policy": "ONE_UNKNOWN_CLAIM_AND_GENERIC_PENDING_TERMINAL",
    "span_policy": "UTF8_BYTE_WITNESS_PLUS_EXISTING_CHARACTER_SPAN",
    "actual_origin_allowed": False,
    "filesystem_access_allowed": False,
    "network_access_allowed": False,
    "environment_access_allowed": False,
    "clock_access_allowed": False,
    "random_access_allowed": False,
    "subprocess_access_allowed": False,
    "ledger_append_allowed": False,
    "contract_manifest_only": True,
    "code_identity_verified": False,
}

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "operation",
        "request_id",
        "parser_run_id",
        "parser_version",
        "parser_manifest_sha256",
        "source_snapshots",
        "input_plan",
        "captures",
    }
)
_CAPTURE_FIELDS = frozenset(
    {
        "input_sequence",
        "registry_record_id",
        "payload_base64",
        "payload_bytes",
        "payload_sha256",
    }
)
_STRUCTURED_ENVELOPE_FIELDS = frozenset(
    {"schema_version", "source_profile", "document", "entries"}
)
_OCR_ENVELOPE_FIELDS = frozenset(
    {
        *_STRUCTURED_ENVELOPE_FIELDS,
        "ocr_source_media_sha256",
        "ocr_engine_manifest_sha256",
    }
)
_ENTRY_FIELDS = frozenset(
    {
        "entry_kind",
        "evidence_start",
        "evidence_end",
        "surface",
        "definition",
    }
)
_WITNESS_FIELDS = frozenset(
    {
        "claim_id",
        "registry_record_id",
        "response_sha256",
        "character_span_start",
        "character_span_end",
        "utf8_byte_span_start",
        "utf8_byte_span_end",
        "span_utf8_sha256",
        "span_canonical_sha256",
    }
)

FALSE_AUTHORITY_FIELDS = frozenset(
    {
        "sandbox_execution_verified",
        "parser_runtime_execution_verified",
        "launch_authority_verified",
        "runtime_noninterference_verified",
        "network_deny_verified",
        "filesystem_write_deny_verified",
        "registry_write_deny_verified",
        "child_process_deny_verified",
        "external_owner_policy_verified",
        "actual_authority_granted",
        "actual_source_claims_credited",
        "actual_a_context_reviews_credited",
        "p0_phase_exit",
        "production_approval",
        "full_scan_approval",
        "action_applied",
    }
)

_RESPONSE_FIELDS = frozenset(
    {
        "schema_version",
        "operation",
        "producer_kind",
        "request_id",
        "parser_run_id",
        "request_sha256",
        "parser_version",
        "parser_manifest_sha256",
        "source_input_plan_sha256",
        "input_registry_sha256",
        "source_claims_jsonl_base64",
        "source_claims_file_bytes",
        "source_claims_file_sha256",
        "source_claim_inventory_sha256",
        "typed_output_claims_sha256",
        "terminal_queue_jsonl_base64",
        "terminal_queue_file_bytes",
        "terminal_queue_file_sha256",
        "terminal_inventory_sha256",
        "generic_queue_sha256",
        "claim_byte_span_witnesses",
        "claim_byte_span_witnesses_sha256",
        "route_classifications",
        "route_classifications_sha256",
        "input_count",
        "processed_count",
        "typed_input_count",
        "typed_claim_row_count",
        "total_claim_row_count",
        "generic_count",
        "error_count",
        "exact_accounting_claimed",
        *FALSE_AUTHORITY_FIELDS,
        "credited_counts",
        "operational_effect",
        "gate_status",
        "response_sha256",
    }
)


class P0SourceProfileParserCandidateError(ValueError):
    """Canonical request or pure transform contract violation."""


class _EnvelopeError(ValueError):
    """One capture cannot be parsed by the fixed envelope grammar."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


PARSER_MANIFEST_SHA256 = canonical_sha256(PARSER_MANIFEST)


def _duplicate_rejecting_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0SourceProfileParserCandidateError(
                "duplicate JSON key is forbidden"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0SourceProfileParserCandidateError(
        f"non-finite JSON number is forbidden: {token}"
    )


def _parse_canonical_object(
    raw: bytes, *, label: str, maximum: int
) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0SourceProfileParserCandidateError(
            f"{label} bytes must be within 1..{maximum}"
        )
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0SourceProfileParserCandidateError(f"{label} must not have BOM")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite,
        )
    except P0SourceProfileParserCandidateError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise P0SourceProfileParserCandidateError(
            f"{label} must be one canonical UTF-8 JSON object"
        ) from exc
    if type(value) is not dict or canonical_file_bytes(value) != raw:
        raise P0SourceProfileParserCandidateError(
            f"{label} must be canonical JSON with one final LF"
        )
    return value


def _exact(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != fields:
        present = set(value) if type(value) is dict else set()
        raise P0SourceProfileParserCandidateError(
            f"{label} fields mismatch: missing={sorted(fields - present)}, "
            f"extra={sorted(present - fields)}"
        )
    return value


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0SourceProfileParserCandidateError(
            f"{field} must be a canonical identifier"
        )
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0SourceProfileParserCandidateError(
            f"{field} must be lowercase SHA-256"
        )
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise P0SourceProfileParserCandidateError(
            f"{field} must be a nonnegative integer"
        )
    return value


def _decode_payload(row: Mapping[str, Any], index: int) -> bytes:
    encoded = row["payload_base64"]
    if not isinstance(encoded, str) or not encoded.isascii():
        raise P0SourceProfileParserCandidateError(
            f"captures[{index}].payload_base64 must be ASCII"
        )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0SourceProfileParserCandidateError(
            f"captures[{index}].payload_base64 is invalid"
        ) from exc
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise P0SourceProfileParserCandidateError(
            f"captures[{index}].payload_base64 is not canonical"
        )
    expected_bytes = _nonnegative_int(
        row["payload_bytes"], f"captures[{index}].payload_bytes"
    )
    if expected_bytes != len(raw) or expected_bytes > MAX_PAYLOAD_BYTES:
        raise P0SourceProfileParserCandidateError(
            f"captures[{index}] payload byte count mismatch"
        )
    expected_sha = _sha(
        row["payload_sha256"], f"captures[{index}].payload_sha256"
    )
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise P0SourceProfileParserCandidateError(
            f"captures[{index}] payload hash mismatch"
        )
    return raw


def parse_request_bytes(raw: bytes) -> dict[str, Any]:
    request = dict(
        _exact(
            _parse_canonical_object(
                raw, label="source-profile parser request", maximum=MAX_REQUEST_BYTES
            ),
            _REQUEST_FIELDS,
            "source-profile parser request",
        )
    )
    if request["schema_version"] != REQUEST_SCHEMA or request["operation"] != OPERATION:
        raise P0SourceProfileParserCandidateError("request schema/operation mismatch")
    _identifier(request["request_id"], "request_id")
    _identifier(request["parser_run_id"], "parser_run_id")
    if request["parser_version"] != PARSER_VERSION:
        raise P0SourceProfileParserCandidateError("parser_version mismatch")
    if _sha(
        request["parser_manifest_sha256"], "parser_manifest_sha256"
    ) != PARSER_MANIFEST_SHA256:
        raise P0SourceProfileParserCandidateError("parser manifest mismatch")

    snapshots = request["source_snapshots"]
    if not isinstance(snapshots, list):
        raise P0SourceProfileParserCandidateError("source_snapshots must be a list")
    try:
        plan = route_contract.validate_source_input_plan(
            request["input_plan"],
            snapshots,
            expected_origin=route_contract.EXAMPLE_ORIGIN,
        )
    except route_contract.P0ActualRouteError as exc:
        raise P0SourceProfileParserCandidateError(
            "source snapshot/input plan contract mismatch"
        ) from exc
    if len(snapshots) != route_contract.EXPECTED_INPUT_COUNT:
        raise P0SourceProfileParserCandidateError("request requires exact 10x4 inputs")

    captures = request["captures"]
    if not isinstance(captures, list) or len(captures) != len(snapshots):
        raise P0SourceProfileParserCandidateError(
            "captures must exactly account for source snapshots"
        )
    source_by_id = {row["registry_record_id"]: row for row in snapshots}
    total = 0
    seen: set[str] = set()
    for index, value in enumerate(captures, start=1):
        capture = _exact(value, _CAPTURE_FIELDS, f"captures[{index - 1}]")
        if capture["input_sequence"] != index:
            raise P0SourceProfileParserCandidateError(
                "capture input_sequence must be contiguous"
            )
        registry_id = _identifier(
            capture["registry_record_id"], f"captures[{index - 1}].registry_record_id"
        )
        if registry_id in seen:
            raise P0SourceProfileParserCandidateError(
                "capture registry_record_id must be unique"
            )
        seen.add(registry_id)
        source = source_by_id.get(registry_id)
        selected = plan["selected_inputs"][index - 1]
        if (
            source is None
            or source["source_id"] != selected["source_id"]
            or source["source_id"] != selected["input_registry_id"]
            or source["source_profile"] != selected["source_profile"]
            or source["capture_profile"] != str(source["source_profile"]).lower()
        ):
            raise P0SourceProfileParserCandidateError(
                "capture/input-plan registry binding mismatch"
            )
        payload = _decode_payload(capture, index - 1)
        total += len(payload)
        if total > MAX_TOTAL_PAYLOAD_BYTES:
            raise P0SourceProfileParserCandidateError(
                "request exceeds total payload byte limit"
            )
        if (
            capture["payload_bytes"] != source["response_bytes"]
            or capture["payload_sha256"] != source["response_sha256"]
            or capture["payload_sha256"] != source["normalized_text_sha256"]
            or source["normalization_version"] != "utf8_identity_v1"
        ):
            raise P0SourceProfileParserCandidateError(
                "capture/source snapshot byte binding mismatch"
            )
    return request


def build_request_bytes(
    *,
    request_id: str,
    parser_run_id: str,
    source_snapshots: Sequence[Mapping[str, Any]],
    input_plan: Mapping[str, Any],
    payloads_by_registry: Mapping[str, bytes],
) -> bytes:
    """Build a canonical path-less request from exact in-memory payload bytes."""

    captures: list[dict[str, Any]] = []
    if set(payloads_by_registry) != {
        str(row["registry_record_id"]) for row in source_snapshots
    }:
        raise P0SourceProfileParserCandidateError(
            "payload mapping must exactly match source registry inputs"
        )
    for sequence, source in enumerate(source_snapshots, start=1):
        registry_id = str(source["registry_record_id"])
        payload = payloads_by_registry[registry_id]
        if type(payload) is not bytes:
            raise P0SourceProfileParserCandidateError(
                "payload mapping values must be exact bytes"
            )
        captures.append(
            {
                "input_sequence": sequence,
                "registry_record_id": registry_id,
                "payload_base64": base64.b64encode(payload).decode("ascii"),
                "payload_bytes": len(payload),
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    request = {
        "schema_version": REQUEST_SCHEMA,
        "operation": OPERATION,
        "request_id": request_id,
        "parser_run_id": parser_run_id,
        "parser_version": PARSER_VERSION,
        "parser_manifest_sha256": PARSER_MANIFEST_SHA256,
        "source_snapshots": [dict(row) for row in source_snapshots],
        "input_plan": dict(input_plan),
        "captures": captures,
    }
    raw = canonical_file_bytes(request)
    parse_request_bytes(raw)
    return raw


def _canonical_text(value: Any, label: str, *, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or unicodedata.normalize("NFC", value) != value
        or '"' in value
        or "\\" in value
        or any(ord(char) < 0x20 for char in value)
    ):
        raise _EnvelopeError(f"{label} must be bounded canonical NFC text")
    return value


def _structured_entries(
    payload: bytes, source_profile: str
) -> tuple[str, list[dict[str, Any]], int]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _EnvelopeError("structured payload must be strict UTF-8") from exc
    if text.startswith("\ufeff") or unicodedata.normalize("NFC", text) != text:
        raise _EnvelopeError("structured payload must be BOM-free NFC")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite,
        )
    except (P0SourceProfileParserCandidateError, json.JSONDecodeError) as exc:
        raise _EnvelopeError("structured payload must be canonical JSON") from exc
    expected_fields = (
        _OCR_ENVELOPE_FIELDS
        if source_profile == "MEDIA_OCR"
        else _STRUCTURED_ENVELOPE_FIELDS
    )
    try:
        envelope = _exact(value, expected_fields, "structured envelope")
    except P0SourceProfileParserCandidateError as exc:
        raise _EnvelopeError("structured envelope field set mismatch") from exc
    if canonical_file_bytes(envelope) != payload:
        raise _EnvelopeError("structured envelope bytes are not canonical")
    if (
        envelope["schema_version"] != ENVELOPE_SCHEMA
        or envelope["source_profile"] != source_profile
    ):
        raise _EnvelopeError("structured envelope schema/profile mismatch")
    if source_profile == "MEDIA_OCR":
        try:
            _sha(envelope["ocr_source_media_sha256"], "ocr_source_media_sha256")
            _sha(
                envelope["ocr_engine_manifest_sha256"],
                "ocr_engine_manifest_sha256",
            )
        except P0SourceProfileParserCandidateError as exc:
            raise _EnvelopeError("MEDIA_OCR provenance hash mismatch") from exc
    document = _canonical_text(
        envelope["document"], "document", maximum=MAX_DOCUMENT_CHARS
    )
    marker = f'"document":"{document}"'
    marker_start = text.find(marker)
    if marker_start < 0 or text.find(marker, marker_start + 1) >= 0:
        raise _EnvelopeError("document marker must occur exactly once")
    document_start = marker_start + len('"document":"')
    entries = envelope["entries"]
    if (
        not isinstance(entries, list)
        or len(entries) != 1
    ):
        raise _EnvelopeError("structured envelope must contain exactly one statement")
    parsed: list[dict[str, Any]] = []
    for index, value_entry in enumerate(entries):
        try:
            entry = _exact(value_entry, _ENTRY_FIELDS, f"entries[{index}]")
        except P0SourceProfileParserCandidateError as exc:
            raise _EnvelopeError("structured entry field set mismatch") from exc
        kind = entry["entry_kind"]
        if kind != ENTRY_EXPLICIT_DEFINITION_CANDIDATE:
            raise _EnvelopeError("structured entry kind is not allowed")
        start = entry["evidence_start"]
        end = entry["evidence_end"]
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise _EnvelopeError("structured evidence offsets are invalid")
        if end > len(document):
            raise _EnvelopeError("structured evidence span is out of range")
        if start != 0 or end != len(document):
            raise _EnvelopeError(
                "structured evidence must cover the complete document"
            )
        evidence = document[start:end]
        surface = _canonical_text(entry["surface"], "surface", maximum=512)
        definition = _canonical_text(
            entry["definition"], "definition", maximum=MAX_DOCUMENT_CHARS
        )
        if evidence != f"'{surface}'은 {definition}을 뜻한다":
            raise _EnvelopeError(
                "structured evidence must match the explicit definition grammar"
            )
        parsed.append(
            {
                "entry_kind": kind,
                "evidence_start": start,
                "evidence_end": end,
                "surface": surface,
                "definition": definition,
            }
        )
    expected_order = sorted(
        parsed,
        key=lambda item: (
            item["evidence_start"],
            item["evidence_end"],
            item["entry_kind"],
            item["surface"],
            item["definition"] or "",
        ),
    )
    if parsed != expected_order or len(
        {
            (
                item["evidence_start"],
                item["evidence_end"],
                item["entry_kind"],
                item["surface"],
                item["definition"],
            )
            for item in parsed
        }
    ) != len(parsed):
        raise _EnvelopeError("structured entries must be ordered and unique")
    return text, parsed, document_start


def _generic_entry(payload: bytes) -> tuple[str, dict[str, Any], int]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _EnvelopeError("generic payload must be strict UTF-8") from exc
    if text.startswith("\ufeff") or "\x00" in text or unicodedata.normalize("NFC", text) != text:
        raise _EnvelopeError("generic payload must be BOM-free NUL-free NFC")
    surface = text.strip()
    if not surface or len(surface) > MAX_DOCUMENT_CHARS:
        raise _EnvelopeError("generic surface must be bounded and non-empty")
    start = text.index(surface)
    return text, {
        "entry_kind": "GENERIC_UNKNOWN",
        "evidence_start": start,
        "evidence_end": start + len(surface),
        "surface": surface,
        "definition": None,
    }, 0


def _claim_id_material(row: Mapping[str, Any], response_sha256: str) -> dict[str, Any]:
    return {
        "domain": "p0-source-profile-claim-id-v1",
        "record_origin": row["record_origin"],
        "registry_record_id": row["registry_record_id"],
        "registry_record_sha256": row["registry_record_sha256"],
        "snapshot_id": row["snapshot_id"],
        "response_sha256": response_sha256,
        "track": row["track"],
        "span_start": row["span_start"],
        "span_end": row["span_end"],
        "span_sha256": row["span_sha256"],
        "normalized_surface": row["normalized_surface"],
        "claim_direction": row["claim_direction"],
        "claim_kind": row["claim_kind"],
        "target_work_id": row["target_work_id"],
        "target_sense_id": row["target_sense_id"],
        "definition": row["definition"],
    }


def _make_claim(
    *,
    source: Mapping[str, Any],
    parser_run_id: str,
    payload_text: str,
    entry: Mapping[str, Any],
    document_start: int,
    generic: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    span_start = document_start + int(entry["evidence_start"])
    span_end = document_start + int(entry["evidence_end"])
    span_text = payload_text[span_start:span_end]
    claim_kind = "UNKNOWN" if generic else "NEW_SENSE_CANDIDATE"
    row: dict[str, Any] = {
        "schema_version": registry_contract.SOURCE_CLAIM_SCHEMA,
        "record_origin": route_contract.EXAMPLE_ORIGIN,
        "claim_id": "PENDING",
        "registry_record_id": source["registry_record_id"],
        "registry_record_sha256": source["registry_record_sha256"],
        "snapshot_id": source["snapshot_id"],
        "track": "B",
        "claim_kind": claim_kind,
        "claim_direction": "UNKNOWN_DIRECTION" if generic else "SURFACE_TO_SENSE",
        "surface_text": entry["surface"],
        "normalized_surface": entry["surface"],
        "target_work_id": None,
        "target_sense_id": None,
        "definition": entry["definition"] if claim_kind == "NEW_SENSE_CANDIDATE" else None,
        "span_start": span_start,
        "span_end": span_end,
        "span_text": span_text,
        "span_sha256": registry_contract.canonical_sha256(span_text),
        "parser_profile": str(source["source_profile"]).lower(),
        "parser_version": PARSER_VERSION,
        "parser_run_id": parser_run_id,
        "parser_manifest_sha256": PARSER_MANIFEST_SHA256,
        "parse_disposition": "GENERIC_PENDING" if generic else "PARSED",
        "repair_mode": "ABSTAIN" if generic else "NONE",
        "repair_output_text": None,
        "repair_source_span_sha256": None,
        "claim_evidence_receipt_sha256": "0" * 64,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    row["claim_id"] = "P0:CLAIM:" + canonical_sha256(
        _claim_id_material(row, str(source["response_sha256"]))
    )
    row["claim_evidence_receipt_sha256"] = registry_contract._claim_receipt(
        row, str(source["response_sha256"])
    )
    row = registry_contract.with_row_hash(row)
    registry_contract._validate_source_claim(
        row,
        route_contract.EXAMPLE_ORIGIN,
        response_sha256=str(source["response_sha256"]),
    )
    utf8_start = len(payload_text[:span_start].encode("utf-8"))
    utf8_end = len(payload_text[:span_end].encode("utf-8"))
    span_raw = payload_text[span_start:span_end].encode("utf-8")
    witness = {
        "claim_id": row["claim_id"],
        "registry_record_id": row["registry_record_id"],
        "response_sha256": source["response_sha256"],
        "character_span_start": span_start,
        "character_span_end": span_end,
        "utf8_byte_span_start": utf8_start,
        "utf8_byte_span_end": utf8_end,
        "span_utf8_sha256": hashlib.sha256(span_raw).hexdigest(),
        "span_canonical_sha256": row["span_sha256"],
    }
    _exact(witness, _WITNESS_FIELDS, "claim byte-span witness")
    return row, witness


def _error_detail(
    source: Mapping[str, Any], *, error_code: str
) -> str:
    return canonical_sha256(
        {
            "domain": "p0-source-profile-parser-error-v1",
            "error_code": error_code,
            "registry_record_id": source["registry_record_id"],
            "response_sha256": source["response_sha256"],
            "parser_version": PARSER_VERSION,
            "parser_manifest_sha256": PARSER_MANIFEST_SHA256,
        }
    )


def _terminal_id_material(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "domain": "p0-source-profile-terminal-id-v1",
        **{
            field: row[field]
            for field in (
                "record_origin",
                "parser_run_id",
                "source_input_plan_sha256",
                "registry_record_id",
                "registry_record_sha256",
                "snapshot_id",
                "source_profile",
                "response_sha256",
                "terminal_disposition",
                "reason_code",
                "error_class",
                "error_detail_sha256",
            )
        },
    }


def _make_terminal(
    *,
    source: Mapping[str, Any],
    parser_run_id: str,
    plan_sha256: str,
    disposition: str,
    reason_code: str,
    error_class: str | None,
    error_detail_sha256: str | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": route_contract.TERMINAL_QUEUE_SCHEMA,
        "record_origin": route_contract.EXAMPLE_ORIGIN,
        "terminal_id": "PENDING",
        "parser_run_id": parser_run_id,
        "source_input_plan_sha256": plan_sha256,
        "registry_record_id": source["registry_record_id"],
        "registry_record_sha256": source["registry_record_sha256"],
        "snapshot_id": source["snapshot_id"],
        "source_profile": source["source_profile"],
        "response_sha256": source["response_sha256"],
        "terminal_disposition": disposition,
        "reason_code": reason_code,
        "error_class": error_class,
        "error_detail_sha256": error_detail_sha256,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    row["terminal_id"] = "P0:TERMINAL:" + canonical_sha256(
        _terminal_id_material(row)
    )
    row = route_contract.with_row_hash(row)
    route_contract.validate_terminal_queue_row(
        row, expected_origin=route_contract.EXAMPLE_ORIGIN
    )
    return row


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_file_bytes(dict(row)) for row in rows)


def execute_request_bytes(raw: bytes) -> bytes:
    """Execute the pure, rejection-only transform for controlled examples."""

    request = parse_request_bytes(raw)
    snapshots = [dict(row) for row in request["source_snapshots"]]
    source_by_id = {row["registry_record_id"]: row for row in snapshots}
    plan = dict(request["input_plan"])
    parser_run_id = str(request["parser_run_id"])
    claims: list[dict[str, Any]] = []
    terminals: list[dict[str, Any]] = []
    witnesses: list[dict[str, Any]] = []
    classifications: list[dict[str, str]] = []

    for capture in request["captures"]:
        source = source_by_id[capture["registry_record_id"]]
        payload = base64.b64decode(capture["payload_base64"], validate=True)
        try:
            if source["source_profile"] == "GENERIC_FALLBACK":
                payload_text, entry, document_start = _generic_entry(payload)
                claim, witness = _make_claim(
                    source=source,
                    parser_run_id=parser_run_id,
                    payload_text=payload_text,
                    entry=entry,
                    document_start=document_start,
                    generic=True,
                )
                claims.append(claim)
                witnesses.append(witness)
                terminals.append(
                    _make_terminal(
                        source=source,
                        parser_run_id=parser_run_id,
                        plan_sha256=str(plan["artifact_sha256"]),
                        disposition="GENERIC_PENDING",
                        reason_code="generic_profile_requires_manual_queue",
                        error_class=None,
                        error_detail_sha256=None,
                    )
                )
                route_class = "GENERIC_PENDING"
            else:
                payload_text, entries, document_start = _structured_entries(
                    payload, str(source["source_profile"])
                )
                for entry in entries:
                    claim, witness = _make_claim(
                        source=source,
                        parser_run_id=parser_run_id,
                        payload_text=payload_text,
                        entry=entry,
                        document_start=document_start,
                        generic=False,
                    )
                    claims.append(claim)
                    witnesses.append(witness)
                route_class = "TYPED"
        except _EnvelopeError:
            terminals.append(
                _make_terminal(
                    source=source,
                    parser_run_id=parser_run_id,
                    plan_sha256=str(plan["artifact_sha256"]),
                    disposition="PARSER_ERROR",
                    reason_code="parser_schema_error",
                    error_class="P0EnvelopeSchemaError",
                    error_detail_sha256=_error_detail(
                        source, error_code="STRUCTURED_OR_GENERIC_SCHEMA_ERROR"
                    ),
                )
            )
            route_class = "PARSER_ERROR"
        classifications.append(
            {
                "registry_record_id": source["registry_record_id"],
                "route_class": route_class,
            }
        )

    claim_order = {
        row["registry_record_id"]: index
        for index, row in enumerate(snapshots)
    }
    claims.sort(
        key=lambda row: (
            claim_order[row["registry_record_id"]],
            row["span_start"],
            row["span_end"],
            row["claim_kind"],
            row["claim_direction"],
            row["normalized_surface"],
            row["definition"] or "",
        )
    )
    witness_by_id = {row["claim_id"]: row for row in witnesses}
    witnesses = [witness_by_id[row["claim_id"]] for row in claims]
    terminals.sort(key=lambda row: claim_order[row["registry_record_id"]])

    typed_claims = [row for row in claims if row["claim_kind"] != "UNKNOWN"]
    generic_claims = [row for row in claims if row["claim_kind"] == "UNKNOWN"]
    source_claims_raw = _jsonl_bytes(claims)
    terminal_raw = _jsonl_bytes(terminals)
    typed_input_count = sum(
        item["route_class"] == "TYPED" for item in classifications
    )
    generic_count = sum(
        item["route_class"] == "GENERIC_PENDING" for item in classifications
    )
    error_count = sum(
        item["route_class"] == "PARSER_ERROR" for item in classifications
    )
    material: dict[str, Any] = {
        "schema_version": RESPONSE_SCHEMA,
        "operation": OPERATION,
        "producer_kind": PRODUCER_KIND,
        "request_id": request["request_id"],
        "parser_run_id": parser_run_id,
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "parser_version": PARSER_VERSION,
        "parser_manifest_sha256": PARSER_MANIFEST_SHA256,
        "source_input_plan_sha256": plan["artifact_sha256"],
        "input_registry_sha256": route_contract.canonical_sha256(snapshots),
        "source_claims_jsonl_base64": base64.b64encode(source_claims_raw).decode(
            "ascii"
        ),
        "source_claims_file_bytes": len(source_claims_raw),
        "source_claims_file_sha256": hashlib.sha256(source_claims_raw).hexdigest(),
        "source_claim_inventory_sha256": route_contract.canonical_sha256(claims),
        "typed_output_claims_sha256": route_contract.canonical_sha256(
            typed_claims
        ),
        "terminal_queue_jsonl_base64": base64.b64encode(terminal_raw).decode(
            "ascii"
        ),
        "terminal_queue_file_bytes": len(terminal_raw),
        "terminal_queue_file_sha256": hashlib.sha256(terminal_raw).hexdigest(),
        "terminal_inventory_sha256": route_contract.canonical_sha256(terminals),
        "generic_queue_sha256": route_contract.canonical_sha256(
            {
                "terminal_rows": terminals,
                "generic_claim_rows": generic_claims,
            }
        ),
        "claim_byte_span_witnesses": witnesses,
        "claim_byte_span_witnesses_sha256": canonical_sha256(witnesses),
        "route_classifications": classifications,
        "route_classifications_sha256": canonical_sha256(classifications),
        "input_count": len(snapshots),
        "processed_count": len(classifications),
        "typed_input_count": typed_input_count,
        "typed_claim_row_count": len(typed_claims),
        "total_claim_row_count": len(claims),
        "generic_count": generic_count,
        "error_count": error_count,
        "exact_accounting_claimed": True,
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    response = {**material, "response_sha256": canonical_sha256(material)}
    encoded = canonical_file_bytes(response)
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise P0SourceProfileParserCandidateError(
            "source-profile parser response exceeds byte limit"
        )
    return encoded


__all__ = [
    "ENVELOPE_SCHEMA",
    "ENTRY_KINDS",
    "ENTRY_EXPLICIT_DEFINITION_CANDIDATE",
    "FALSE_AUTHORITY_FIELDS",
    "GATE_STATUS",
    "MAX_DOCUMENT_CHARS",
    "OPERATION",
    "PARSER_MANIFEST",
    "PARSER_MANIFEST_SHA256",
    "PARSER_VERSION",
    "PRODUCER_KIND",
    "P0SourceProfileParserCandidateError",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "build_request_bytes",
    "canonical_bytes",
    "canonical_file_bytes",
    "canonical_sha256",
    "execute_request_bytes",
    "parse_request_bytes",
]
