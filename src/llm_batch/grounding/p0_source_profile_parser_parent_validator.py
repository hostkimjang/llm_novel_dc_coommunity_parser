"""Independent parent replay for pure source-profile parser artifacts.

The validator intentionally does not call the candidate producer.  It parses
the request and response again, derives expected claims/terminals from capture
bytes, replays UTF-8 byte/character spans, and then runs the existing registry
and route validators.  A successful receipt is structural evidence only.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping

from llm_batch.grounding import p0_actual_registry_contract as registry_contract
from llm_batch.grounding import p0_actual_route_contract as route_contract
from llm_batch.grounding import p0_source_profile_parser_candidate as candidate


VALIDATION_RECEIPT_SCHEMA = (
    "p0_source_profile_parser_parent_validation_receipt_v1"
)
GATE_STATUS = "EXACT_ENVELOPE_PROJECTION_REPLAY_PASS_SOURCE_PARSER_AUTHORITY_NO_GO"

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
        *candidate.FALSE_AUTHORITY_FIELDS,
        "credited_counts",
        "operational_effect",
        "gate_status",
        "response_sha256",
    }
)
_STRUCTURED_FIELDS = frozenset(
    {"schema_version", "source_profile", "document", "entries"}
)
_OCR_FIELDS = frozenset(
    {
        *_STRUCTURED_FIELDS,
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


class P0SourceProfileParserParentValidationError(ValueError):
    """Presented producer artifact failed independent parent replay."""


class _ExpectedParserError(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_file_bytes(value: Any) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0SourceProfileParserParentValidationError(
                "duplicate JSON key is forbidden"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0SourceProfileParserParentValidationError(
        f"non-finite JSON number is forbidden: {token}"
    )


def _parse_object(raw: bytes, *, label: str, maximum: int) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0SourceProfileParserParentValidationError(
            f"{label} bytes are outside the bounded contract"
        )
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0SourceProfileParserParentValidationError(f"{label} has a BOM")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except P0SourceProfileParserParentValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise P0SourceProfileParserParentValidationError(
            f"{label} is not one canonical UTF-8 object"
        ) from exc
    if type(value) is not dict or _canonical_file_bytes(value) != raw:
        raise P0SourceProfileParserParentValidationError(
            f"{label} is not canonical JSON with one final LF"
        )
    return value


def _exact(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0SourceProfileParserParentValidationError(
            f"{label} exact field set mismatch"
        )
    return value


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0SourceProfileParserParentValidationError(
            f"{field} is not a canonical identifier"
        )
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0SourceProfileParserParentValidationError(
            f"{field} is not lowercase SHA-256"
        )
    return value


def _int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise P0SourceProfileParserParentValidationError(
            f"{field} is not a nonnegative integer"
        )
    return value


def _decode_base64(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or not value.isascii():
        raise P0SourceProfileParserParentValidationError(
            f"{label} must be ASCII base64"
        )
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0SourceProfileParserParentValidationError(
            f"{label} is invalid base64"
        ) from exc
    if base64.b64encode(raw).decode("ascii") != value:
        raise P0SourceProfileParserParentValidationError(
            f"{label} is noncanonical base64"
        )
    return raw


def _parse_request_independent(raw: bytes) -> tuple[dict[str, Any], list[bytes]]:
    request = dict(
        _exact(
            _parse_object(raw, label="parser request", maximum=candidate.MAX_REQUEST_BYTES),
            _REQUEST_FIELDS,
            "parser request",
        )
    )
    if (
        request["schema_version"] != candidate.REQUEST_SCHEMA
        or request["operation"] != candidate.OPERATION
        or request["parser_version"] != candidate.PARSER_VERSION
        or request["parser_manifest_sha256"]
        != candidate.PARSER_MANIFEST_SHA256
    ):
        raise P0SourceProfileParserParentValidationError(
            "parser request fixed contract mismatch"
        )
    _identifier(request["request_id"], "request_id")
    _identifier(request["parser_run_id"], "parser_run_id")
    snapshots = request["source_snapshots"]
    if not isinstance(snapshots, list):
        raise P0SourceProfileParserParentValidationError(
            "source_snapshots must be a list"
        )
    try:
        plan = route_contract.validate_source_input_plan(
            request["input_plan"],
            snapshots,
            expected_origin=route_contract.EXAMPLE_ORIGIN,
        )
    except route_contract.P0ActualRouteError as exc:
        raise P0SourceProfileParserParentValidationError(
            "request plan/snapshot contract mismatch"
        ) from exc
    captures = request["captures"]
    if (
        not isinstance(captures, list)
        or len(captures) != route_contract.EXPECTED_INPUT_COUNT
        or len(snapshots) != route_contract.EXPECTED_INPUT_COUNT
    ):
        raise P0SourceProfileParserParentValidationError(
            "request input accounting mismatch"
        )
    source_by_id = {row["registry_record_id"]: row for row in snapshots}
    payloads: list[bytes] = []
    total = 0
    seen: set[str] = set()
    for index, value in enumerate(captures, start=1):
        capture = _exact(value, _CAPTURE_FIELDS, f"captures[{index - 1}]")
        if capture["input_sequence"] != index:
            raise P0SourceProfileParserParentValidationError(
                "capture order mismatch"
            )
        registry_id = _identifier(capture["registry_record_id"], "registry_record_id")
        if registry_id in seen:
            raise P0SourceProfileParserParentValidationError(
                "duplicate capture registry id"
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
            raise P0SourceProfileParserParentValidationError(
                "capture/plan/source binding mismatch"
            )
        payload = _decode_base64(capture["payload_base64"], "payload_base64")
        payload_bytes = _int(capture["payload_bytes"], "payload_bytes")
        payload_sha = _sha(capture["payload_sha256"], "payload_sha256")
        total += len(payload)
        if (
            payload_bytes != len(payload)
            or payload_bytes > candidate.MAX_PAYLOAD_BYTES
            or payload_sha != hashlib.sha256(payload).hexdigest()
            or payload_bytes != source["response_bytes"]
            or payload_sha != source["response_sha256"]
            or payload_sha != source["normalized_text_sha256"]
            or source["normalization_version"] != "utf8_identity_v1"
            or total > candidate.MAX_TOTAL_PAYLOAD_BYTES
        ):
            raise P0SourceProfileParserParentValidationError(
                "capture byte/source binding mismatch"
            )
        payloads.append(payload)
    return request, payloads


def _parse_jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise P0SourceProfileParserParentValidationError(
            f"{label} must end with LF"
        )
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw.splitlines(keepends=True)):
        rows.append(
            _parse_object(
                line,
                label=f"{label}[{index}]",
                maximum=candidate.MAX_RESPONSE_BYTES,
            )
        )
    if b"".join(_canonical_file_bytes(row) for row in rows) != raw:
        raise P0SourceProfileParserParentValidationError(
            f"{label} is not canonical JSONL"
        )
    return rows


def _canonical_text(value: Any, label: str, maximum: int) -> str:
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
        raise _ExpectedParserError(f"{label} is not canonical text")
    return value


def _independent_entries(
    payload: bytes, profile: str
) -> tuple[str, list[dict[str, Any]], int, bool]:
    if profile == "GENERIC_FALLBACK":
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise _ExpectedParserError("generic UTF-8") from exc
        if (
            text.startswith("\ufeff")
            or "\x00" in text
            or unicodedata.normalize("NFC", text) != text
        ):
            raise _ExpectedParserError("generic normalization")
        surface = text.strip()
        if not surface or len(surface) > candidate.MAX_DOCUMENT_CHARS:
            raise _ExpectedParserError("generic length")
        start = text.index(surface)
        return text, [
            {
                "entry_kind": "GENERIC_UNKNOWN",
                "evidence_start": start,
                "evidence_end": start + len(surface),
                "surface": surface,
                "definition": None,
            }
        ], 0, True

    try:
        text = payload.decode("utf-8", errors="strict")
        envelope = json.loads(
            text,
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        P0SourceProfileParserParentValidationError,
    ) as exc:
        raise _ExpectedParserError("structured JSON") from exc
    fields = _OCR_FIELDS if profile == "MEDIA_OCR" else _STRUCTURED_FIELDS
    if (
        type(envelope) is not dict
        or set(envelope) != fields
        or _canonical_file_bytes(envelope) != payload
        or text.startswith("\ufeff")
        or unicodedata.normalize("NFC", text) != text
        or envelope["schema_version"] != candidate.ENVELOPE_SCHEMA
        or envelope["source_profile"] != profile
    ):
        raise _ExpectedParserError("structured envelope")
    if profile == "MEDIA_OCR":
        for field in ("ocr_source_media_sha256", "ocr_engine_manifest_sha256"):
            value = envelope[field]
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise _ExpectedParserError("OCR provenance")
    document = _canonical_text(
        envelope["document"], "document", candidate.MAX_DOCUMENT_CHARS
    )
    marker = f'"document":"{document}"'
    marker_start = text.find(marker)
    if marker_start < 0 or text.find(marker, marker_start + 1) >= 0:
        raise _ExpectedParserError("document marker")
    base = marker_start + len('"document":"')
    values = envelope["entries"]
    if (
        not isinstance(values, list)
        or len(values) != 1
    ):
        raise _ExpectedParserError("exactly one statement")
    entries: list[dict[str, Any]] = []
    for value in values:
        if type(value) is not dict or set(value) != _ENTRY_FIELDS:
            raise _ExpectedParserError("entry fields")
        kind = value["entry_kind"]
        start = value["evidence_start"]
        end = value["evidence_end"]
        if (
            kind != candidate.ENTRY_EXPLICIT_DEFINITION_CANDIDATE
            or type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
            or end > len(document)
            or start != 0
            or end != len(document)
        ):
            raise _ExpectedParserError("entry coordinates")
        surface = _canonical_text(value["surface"], "surface", 512)
        definition = _canonical_text(
            value["definition"], "definition", candidate.MAX_DOCUMENT_CHARS
        )
        evidence = document[start:end]
        if evidence != f"'{surface}'은 {definition}을 뜻한다":
            raise _ExpectedParserError("explicit definition grammar")
        entries.append(
            {
                "entry_kind": kind,
                "evidence_start": start,
                "evidence_end": end,
                "surface": surface,
                "definition": definition,
            }
        )
    ordered = sorted(
        entries,
        key=lambda item: (
            item["evidence_start"],
            item["evidence_end"],
            item["entry_kind"],
            item["surface"],
            item["definition"] or "",
        ),
    )
    units = {
        (
            item["evidence_start"],
            item["evidence_end"],
            item["entry_kind"],
            item["surface"],
            item["definition"],
        )
        for item in entries
    }
    if entries != ordered or len(units) != len(entries):
        raise _ExpectedParserError("entry order/uniqueness")
    return text, entries, base, False


def _claim_id_material(row: Mapping[str, Any], response_sha: str) -> dict[str, Any]:
    return {
        "domain": "p0-source-profile-claim-id-v1",
        "record_origin": row["record_origin"],
        "registry_record_id": row["registry_record_id"],
        "registry_record_sha256": row["registry_record_sha256"],
        "snapshot_id": row["snapshot_id"],
        "response_sha256": response_sha,
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


def _expected_claim(
    source: Mapping[str, Any],
    parser_run_id: str,
    payload_text: str,
    entry: Mapping[str, Any],
    base: int,
    generic: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    start = base + int(entry["evidence_start"])
    end = base + int(entry["evidence_end"])
    span = payload_text[start:end]
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
        "span_start": start,
        "span_end": end,
        "span_text": span,
        "span_sha256": registry_contract.canonical_sha256(span),
        "parser_profile": str(source["source_profile"]).lower(),
        "parser_version": candidate.PARSER_VERSION,
        "parser_run_id": parser_run_id,
        "parser_manifest_sha256": candidate.PARSER_MANIFEST_SHA256,
        "parse_disposition": "GENERIC_PENDING" if generic else "PARSED",
        "repair_mode": "ABSTAIN" if generic else "NONE",
        "repair_output_text": None,
        "repair_source_span_sha256": None,
        "claim_evidence_receipt_sha256": "0" * 64,
        "action_applied": False,
        "operational_effect": registry_contract.OPERATIONAL_EFFECT,
    }
    row["claim_id"] = "P0:CLAIM:" + _canonical_sha256(
        _claim_id_material(row, str(source["response_sha256"]))
    )
    row["claim_evidence_receipt_sha256"] = registry_contract._claim_receipt(
        row, str(source["response_sha256"])
    )
    row = registry_contract.with_row_hash(row)
    byte_start = len(payload_text[:start].encode("utf-8"))
    byte_end = len(payload_text[:end].encode("utf-8"))
    witness = {
        "claim_id": row["claim_id"],
        "registry_record_id": row["registry_record_id"],
        "response_sha256": source["response_sha256"],
        "character_span_start": start,
        "character_span_end": end,
        "utf8_byte_span_start": byte_start,
        "utf8_byte_span_end": byte_end,
        "span_utf8_sha256": hashlib.sha256(span.encode("utf-8")).hexdigest(),
        "span_canonical_sha256": row["span_sha256"],
    }
    return row, witness


def _error_detail(source: Mapping[str, Any]) -> str:
    return _canonical_sha256(
        {
            "domain": "p0-source-profile-parser-error-v1",
            "error_code": "STRUCTURED_OR_GENERIC_SCHEMA_ERROR",
            "registry_record_id": source["registry_record_id"],
            "response_sha256": source["response_sha256"],
            "parser_version": candidate.PARSER_VERSION,
            "parser_manifest_sha256": candidate.PARSER_MANIFEST_SHA256,
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


def _expected_terminal(
    source: Mapping[str, Any],
    parser_run_id: str,
    plan_sha: str,
    *,
    error: bool,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": route_contract.TERMINAL_QUEUE_SCHEMA,
        "record_origin": route_contract.EXAMPLE_ORIGIN,
        "terminal_id": "PENDING",
        "parser_run_id": parser_run_id,
        "source_input_plan_sha256": plan_sha,
        "registry_record_id": source["registry_record_id"],
        "registry_record_sha256": source["registry_record_sha256"],
        "snapshot_id": source["snapshot_id"],
        "source_profile": source["source_profile"],
        "response_sha256": source["response_sha256"],
        "terminal_disposition": "PARSER_ERROR" if error else "GENERIC_PENDING",
        "reason_code": "parser_schema_error" if error else "generic_profile_requires_manual_queue",
        "error_class": "P0EnvelopeSchemaError" if error else None,
        "error_detail_sha256": _error_detail(source) if error else None,
        "action_applied": False,
        "operational_effect": registry_contract.OPERATIONAL_EFFECT,
    }
    row["terminal_id"] = "P0:TERMINAL:" + _canonical_sha256(
        _terminal_id_material(row)
    )
    return route_contract.with_row_hash(row)


def _derive_expected(
    request: Mapping[str, Any], payloads: list[bytes]
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, str]],
]:
    snapshots = [dict(row) for row in request["source_snapshots"]]
    parser_run_id = str(request["parser_run_id"])
    plan_sha = str(request["input_plan"]["artifact_sha256"])
    claims: list[dict[str, Any]] = []
    terminals: list[dict[str, Any]] = []
    witnesses: list[dict[str, Any]] = []
    classifications: list[dict[str, str]] = []
    for source, payload in zip(snapshots, payloads):
        try:
            text, entries, base, generic = _independent_entries(
                payload, str(source["source_profile"])
            )
            for entry in entries:
                claim, witness = _expected_claim(
                    source, parser_run_id, text, entry, base, generic
                )
                claims.append(claim)
                witnesses.append(witness)
            if generic:
                terminals.append(
                    _expected_terminal(source, parser_run_id, plan_sha, error=False)
                )
                route_class = "GENERIC_PENDING"
            else:
                route_class = "TYPED"
        except _ExpectedParserError:
            terminals.append(
                _expected_terminal(source, parser_run_id, plan_sha, error=True)
            )
            route_class = "PARSER_ERROR"
        classifications.append(
            {
                "registry_record_id": source["registry_record_id"],
                "route_class": route_class,
            }
        )
    order = {row["registry_record_id"]: index for index, row in enumerate(snapshots)}
    claims.sort(
        key=lambda row: (
            order[row["registry_record_id"]],
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
    terminals.sort(key=lambda row: order[row["registry_record_id"]])
    return claims, terminals, witnesses, classifications


def validate_response_against_request(
    response_raw: bytes, request_raw: bytes
) -> dict[str, Any]:
    request, payloads = _parse_request_independent(request_raw)
    response = dict(
        _exact(
            _parse_object(
                response_raw,
                label="parser response",
                maximum=candidate.MAX_RESPONSE_BYTES,
            ),
            _RESPONSE_FIELDS,
            "parser response",
        )
    )
    if (
        response["schema_version"] != candidate.RESPONSE_SCHEMA
        or response["operation"] != candidate.OPERATION
        or response["producer_kind"] != candidate.PRODUCER_KIND
        or response["request_id"] != request["request_id"]
        or response["parser_run_id"] != request["parser_run_id"]
        or response["request_sha256"] != hashlib.sha256(request_raw).hexdigest()
        or response["parser_version"] != candidate.PARSER_VERSION
        or response["parser_manifest_sha256"]
        != candidate.PARSER_MANIFEST_SHA256
        or response["source_input_plan_sha256"]
        != request["input_plan"]["artifact_sha256"]
        or response["input_registry_sha256"]
        != route_contract.canonical_sha256(request["source_snapshots"])
    ):
        raise P0SourceProfileParserParentValidationError(
            "response/request fixed echo mismatch"
        )
    for field in (
        "request_sha256",
        "parser_manifest_sha256",
        "source_input_plan_sha256",
        "input_registry_sha256",
        "source_claims_file_sha256",
        "source_claim_inventory_sha256",
        "typed_output_claims_sha256",
        "terminal_queue_file_sha256",
        "terminal_inventory_sha256",
        "generic_queue_sha256",
        "claim_byte_span_witnesses_sha256",
        "route_classifications_sha256",
        "response_sha256",
    ):
        _sha(response[field], field)
    if (
        any(response[field] is not False for field in candidate.FALSE_AUTHORITY_FIELDS)
        or response["credited_counts"]
        != {"actual_source_claim_count": 0, "actual_a_context_review_count": 0}
        or response["operational_effect"] != registry_contract.OPERATIONAL_EFFECT
        or response["gate_status"] != candidate.GATE_STATUS
        or response["exact_accounting_claimed"] is not True
    ):
        raise P0SourceProfileParserParentValidationError(
            "response authority/gate invariant mismatch"
        )
    material = {key: value for key, value in response.items() if key != "response_sha256"}
    if response["response_sha256"] != _canonical_sha256(material):
        raise P0SourceProfileParserParentValidationError(
            "response self hash mismatch"
        )

    claim_raw = _decode_base64(
        response["source_claims_jsonl_base64"], "source claims JSONL"
    )
    terminal_raw = _decode_base64(
        response["terminal_queue_jsonl_base64"], "terminal queue JSONL"
    )
    claims = _parse_jsonl(claim_raw, "source claims")
    terminals = _parse_jsonl(terminal_raw, "terminal queue")
    expected_claims, expected_terminals, expected_witnesses, expected_classes = (
        _derive_expected(request, payloads)
    )
    if claims != expected_claims:
        raise P0SourceProfileParserParentValidationError(
            "source claim output differs from independent capture replay"
        )
    if terminals != expected_terminals:
        raise P0SourceProfileParserParentValidationError(
            "terminal output differs from independent capture replay"
        )
    if response["claim_byte_span_witnesses"] != expected_witnesses:
        raise P0SourceProfileParserParentValidationError(
            "byte-span witnesses differ from independent replay"
        )
    if response["route_classifications"] != expected_classes:
        raise P0SourceProfileParserParentValidationError(
            "route classifications differ from independent replay"
        )
    for witness in expected_witnesses:
        _exact(witness, _WITNESS_FIELDS, "claim byte-span witness")

    source_by_id = {
        row["registry_record_id"]: row for row in request["source_snapshots"]
    }
    for row in claims:
        source = source_by_id[row["registry_record_id"]]
        try:
            registry_contract._validate_source_claim(
                row,
                route_contract.EXAMPLE_ORIGIN,
                response_sha256=str(source["response_sha256"]),
            )
        except registry_contract.P0ActualContractError as exc:
            raise P0SourceProfileParserParentValidationError(
                "source claim contract replay failed"
            ) from exc
    for row in terminals:
        try:
            route_contract.validate_terminal_queue_row(
                row, expected_origin=route_contract.EXAMPLE_ORIGIN
            )
        except route_contract.P0ActualRouteError as exc:
            raise P0SourceProfileParserParentValidationError(
                "terminal contract replay failed"
            ) from exc

    typed = [row for row in claims if row["claim_kind"] != "UNKNOWN"]
    generic = [row for row in claims if row["claim_kind"] == "UNKNOWN"]
    typed_input_count = sum(row["route_class"] == "TYPED" for row in expected_classes)
    generic_count = sum(
        row["route_class"] == "GENERIC_PENDING" for row in expected_classes
    )
    error_count = sum(
        row["route_class"] == "PARSER_ERROR" for row in expected_classes
    )
    expected_scalars = {
        "source_claims_file_bytes": len(claim_raw),
        "source_claims_file_sha256": hashlib.sha256(claim_raw).hexdigest(),
        "source_claim_inventory_sha256": route_contract.canonical_sha256(claims),
        "typed_output_claims_sha256": route_contract.canonical_sha256(typed),
        "terminal_queue_file_bytes": len(terminal_raw),
        "terminal_queue_file_sha256": hashlib.sha256(terminal_raw).hexdigest(),
        "terminal_inventory_sha256": route_contract.canonical_sha256(terminals),
        "generic_queue_sha256": route_contract.canonical_sha256(
            {"terminal_rows": terminals, "generic_claim_rows": generic}
        ),
        "claim_byte_span_witnesses_sha256": _canonical_sha256(expected_witnesses),
        "route_classifications_sha256": _canonical_sha256(expected_classes),
        "input_count": route_contract.EXPECTED_INPUT_COUNT,
        "processed_count": route_contract.EXPECTED_INPUT_COUNT,
        "typed_input_count": typed_input_count,
        "typed_claim_row_count": len(typed),
        "total_claim_row_count": len(claims),
        "generic_count": generic_count,
        "error_count": error_count,
    }
    mismatches = [
        field
        for field, expected in expected_scalars.items()
        if response.get(field) != expected
    ]
    if mismatches:
        raise P0SourceProfileParserParentValidationError(
            "response artifact/count binding mismatch: " + ",".join(sorted(mismatches))
        )

    receipt_material = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "request_sha256": hashlib.sha256(request_raw).hexdigest(),
        "response_bytes_sha256": hashlib.sha256(response_raw).hexdigest(),
        "producer_response_sha256": response["response_sha256"],
        "parser_version": candidate.PARSER_VERSION,
        "parser_manifest_sha256": candidate.PARSER_MANIFEST_SHA256,
        "source_input_plan_sha256": response["source_input_plan_sha256"],
        "input_registry_sha256": response["input_registry_sha256"],
        "source_claim_inventory_sha256": response[
            "source_claim_inventory_sha256"
        ],
        "terminal_inventory_sha256": response["terminal_inventory_sha256"],
        "claim_byte_span_witnesses_sha256": response[
            "claim_byte_span_witnesses_sha256"
        ],
        "input_count": response["input_count"],
        "typed_input_count": response["typed_input_count"],
        "typed_claim_row_count": response["typed_claim_row_count"],
        "generic_count": response["generic_count"],
        "error_count": response["error_count"],
        "presented_envelope_projection_contract_verified": True,
        "parent_independent_presented_payload_projection_replay_verified": True,
        "utf8_byte_and_character_span_cross_binding_verified": True,
        "exact_one_route_accounting_verified": True,
        **{field: False for field in candidate.FALSE_AUTHORITY_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": registry_contract.OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    return {
        **receipt_material,
        "receipt_sha256": _canonical_sha256(receipt_material),
    }


def validated_artifacts(
    response_raw: bytes, request_raw: bytes
) -> dict[str, Any]:
    """Return validated rows after independent replay, without writing files."""

    receipt = validate_response_against_request(response_raw, request_raw)
    response = _parse_object(
        response_raw,
        label="parser response",
        maximum=candidate.MAX_RESPONSE_BYTES,
    )
    return {
        "receipt": receipt,
        "source_claims": _parse_jsonl(
            _decode_base64(
                response["source_claims_jsonl_base64"], "source claims JSONL"
            ),
            "source claims",
        ),
        "terminal_rows": _parse_jsonl(
            _decode_base64(
                response["terminal_queue_jsonl_base64"], "terminal queue JSONL"
            ),
            "terminal queue",
        ),
    }


__all__ = [
    "GATE_STATUS",
    "P0SourceProfileParserParentValidationError",
    "VALIDATION_RECEIPT_SCHEMA",
    "validate_response_against_request",
    "validated_artifacts",
]
