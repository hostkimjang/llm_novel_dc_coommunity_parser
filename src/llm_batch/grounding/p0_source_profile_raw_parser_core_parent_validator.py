"""Separate-implementation parent replay for the neutral observation core.

This module does not call ``parse_capture`` or producer helpers.  It repeats
the bounded UTF-8/profile/whole-line grammar and exact span derivation before
accepting a presented result.  Success proves only presented payload replay;
it is not process, source-adapter, semantic, owner, ledger, or P0 authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping

VALIDATION_RECEIPT_SCHEMA = "p0_raw_capture_core_parent_validation_receipt_v1"
GATE_STATUS = "RAW_CAPTURE_NEUTRAL_OBSERVATION_REPLAY_PASS_RUNTIME_AUTHORITY_NO_GO"
RESULT_SCHEMA = "p0_raw_capture_neutral_observation_result_v1"
OBSERVATION_SCHEMA = "p0_raw_capture_neutral_observation_v1"
CORE_MANIFEST_SCHEMA = "p0_raw_capture_parser_core_manifest_v1"
EXPECTED_CORE_VERSION = "raw-captured-utf8-neutral-observation-core-v1"
MAX_PAYLOAD_BYTES = 256 * 1024
MAX_DOCUMENT_CHARS = 64 * 1024
MAX_OBSERVATIONS = 64
MAX_SURFACE_CHARS = 512
MAX_DEFINITION_CHARS = 4096
MAX_METADATA_CHARS = 512

_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "core_version",
        "core_manifest_sha256",
        "source_profile",
        "content_type",
        "capture_version",
        "normalization_version",
        "payload_bytes",
        "payload_sha256",
        "disposition",
        "reason_code",
        "line_count",
        "nonempty_line_count",
        "observation_count",
        "observations",
        "observations_sha256",
        "result_sha256",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version",
        "observation_sequence",
        "line_number",
        "relation_kind",
        "character_span_start",
        "character_span_end",
        "utf8_byte_span_start",
        "utf8_byte_span_end",
        "evidence_text",
        "evidence_utf8_sha256",
        "surface_text",
        "surface_utf8_sha256",
        "presented_definition_text",
        "presented_definition_utf8_sha256",
        "observation_sha256",
    }
)
_RELATIONS = (
    re.compile(
        r"^'(?P<surface>[^'\n]{1,512})'(?:은|는) "
        r"(?P<presented_definition>.+?)(?:을|를) 뜻한다\.$"
    ),
)
_FORBIDDEN_DOCUMENT_FORMAT_CHARACTERS = ("\u200b", "\u200c", "\u200d", "\ufeff")
_FORBIDDEN_INVISIBLE = frozenset(_FORBIDDEN_DOCUMENT_FORMAT_CHARACTERS)
_FORBIDDEN_RELATION_CHARACTERS = frozenset(
    {"'", '"', "\\", ".", "?", "!", "。", "！", "？", "\u2026"}
)
_FORBIDDEN_RELATION_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_RELATION_GRAMMARS = (
    "'<surface>'은 <presented_definition_text>을 뜻한다.",
    "'<surface>'은 <presented_definition_text>를 뜻한다.",
    "'<surface>'는 <presented_definition_text>을 뜻한다.",
    "'<surface>'는 <presented_definition_text>를 뜻한다.",
)
_DISPOSITIONS = (
    "MATCHED",
    "NO_MATCH",
    "UNSUPPORTED_PROFILE",
    "INVALID_CAPTURE",
)
_REASON_CODES = (
    "all_nonempty_lines_are_explicit_definition_observations",
    "no_nonempty_statement",
    "mixed_or_nonmatching_context_fail_closed",
    "official_capture_adapter_not_bound",
    "ocr_media_engine_transcript_provenance_not_bound",
    "generic_profile_requires_manual_lane",
    "unknown_source_profile",
    "community_capture_contract_mismatch",
    "empty_payload",
    "payload_byte_limit_exceeded",
    "invalid_utf8",
    "utf8_bom_forbidden",
    "nul_forbidden",
    "non_lf_line_ending",
    "document_character_limit_exceeded",
    "document_not_nfc",
    "invisible_format_character_forbidden",
    "observation_limit_exceeded",
)


class P0RawCaptureCoreParentValidationError(ValueError):
    """A presented core result differed from independent parent replay."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


_EXPECTED_CORE_MANIFEST: dict[str, Any] = {
    "schema_version": CORE_MANIFEST_SCHEMA,
    "core_version": EXPECTED_CORE_VERSION,
    "result_schema": RESULT_SCHEMA,
    "observation_schema": OBSERVATION_SCHEMA,
    "supported_capture_contract": {
        "source_profile": "COMMUNITY_STRUCTURED",
        "content_type": "text/plain; charset=utf-8",
        "capture_version": "normalized-community-explicit-statement-lines-v1",
        "normalization_version": "utf8_identity_v1",
    },
    "unsupported_profiles": [
        "OFFICIAL_STRUCTURED",
        "MEDIA_OCR",
        "GENERIC_FALLBACK",
    ],
    "relation_grammars": list(_RELATION_GRAMMARS),
    "match_boundary_policy": "ALL_NONEMPTY_LINES_MUST_MATCH_WHOLE_LINE",
    "line_policy": "LF_ONLY_FINAL_LF_OPTIONAL_BLANK_LINES_ALLOWED",
    "dispositions": list(_DISPOSITIONS),
    "reason_codes": list(_REASON_CODES),
    "metadata_policy": {
        "max_chars": MAX_METADATA_CHARS,
        "nfc_required": True,
        "trimmed_nonempty_required": True,
        "forbidden_unicode_categories": sorted(_FORBIDDEN_RELATION_CATEGORIES),
    },
    "relation_text_policy": {
        "forbidden_characters": [
            "'", '"', "\\", ".", "?", "!", "。", "！", "？", "\u2026"
        ],
        "forbidden_unicode_categories": sorted(_FORBIDDEN_RELATION_CATEGORIES),
    },
    "document_policy": {
        "forbidden_format_characters": list(
            _FORBIDDEN_DOCUMENT_FORMAT_CHARACTERS
        ),
        "nfc_required": True,
        "bom_forbidden": True,
        "nul_forbidden": True,
    },
    "output_policy": "NEUTRAL_OBSERVATIONS_ONLY_NO_CLAIM_ROUTE_TARGET_OR_CREDIT",
    "raw_input_truth": "PRESENTED_CAPTURE_BYTES_NOT_HTTP_WIRE_OR_SOURCE_ADAPTER_AUTHORITY",
    "manifest_scope": "DECLARED_BEHAVIOR_CONTRACT_NOT_CODE_IDENTITY",
    "limits": {
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "max_document_chars": MAX_DOCUMENT_CHARS,
        "max_observations": MAX_OBSERVATIONS,
        "max_surface_chars": MAX_SURFACE_CHARS,
        "max_definition_chars": MAX_DEFINITION_CHARS,
    },
    "direct_io_capabilities": [],
    "capture_adapter_authority_verified": False,
    "ocr_transcription_provenance_verified": False,
    "code_identity_verified": False,
    "dependency_closure_verified": False,
}
EXPECTED_CORE_MANIFEST_SHA256 = _canonical_sha256(_EXPECTED_CORE_MANIFEST)


def _metadata(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_METADATA_CHARS
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
        or any(
            char in _FORBIDDEN_INVISIBLE
            or unicodedata.category(char) in _FORBIDDEN_RELATION_CATEGORIES
            for char in value
        )
    ):
        raise P0RawCaptureCoreParentValidationError(
            f"{field} must be canonical text"
        )
    return value


def _relation_text(value: str, maximum: int) -> bool:
    return (
        bool(value)
        and len(value) <= maximum
        and value == value.strip()
        and unicodedata.normalize("NFC", value) == value
        and not any(
            char in _FORBIDDEN_RELATION_CHARACTERS
            or char in _FORBIDDEN_INVISIBLE
            or unicodedata.category(char) in _FORBIDDEN_RELATION_CATEGORIES
            for char in value
        )
    )


def _unsupported_reason(
    source_profile: str,
    content_type: str,
    capture_version: str,
    normalization_version: str,
) -> str | None:
    if source_profile == "OFFICIAL_STRUCTURED":
        return "official_capture_adapter_not_bound"
    if source_profile == "MEDIA_OCR":
        return "ocr_media_engine_transcript_provenance_not_bound"
    if source_profile == "GENERIC_FALLBACK":
        return "generic_profile_requires_manual_lane"
    if source_profile != "COMMUNITY_STRUCTURED":
        return "unknown_source_profile"
    if (
        content_type != "text/plain; charset=utf-8"
        or capture_version
        != "normalized-community-explicit-statement-lines-v1"
        or normalization_version != "utf8_identity_v1"
    ):
        return "community_capture_contract_mismatch"
    return None


def _result(
    *,
    source_profile: str,
    content_type: str,
    capture_version: str,
    normalization_version: str,
    payload: bytes,
    disposition: str,
    reason_code: str,
    line_count: int,
    nonempty_line_count: int,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    material: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA,
        "core_version": EXPECTED_CORE_VERSION,
        "core_manifest_sha256": EXPECTED_CORE_MANIFEST_SHA256,
        "source_profile": source_profile,
        "content_type": content_type,
        "capture_version": capture_version,
        "normalization_version": normalization_version,
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "disposition": disposition,
        "reason_code": reason_code,
        "line_count": line_count,
        "nonempty_line_count": nonempty_line_count,
        "observation_count": len(observations),
        "observations": observations,
        "observations_sha256": _canonical_sha256(observations),
    }
    return {**material, "result_sha256": _canonical_sha256(material)}


def _invalid(
    *,
    source_profile: str,
    content_type: str,
    capture_version: str,
    normalization_version: str,
    payload: bytes,
    reason_code: str,
) -> dict[str, Any]:
    return _result(
        source_profile=source_profile,
        content_type=content_type,
        capture_version=capture_version,
        normalization_version=normalization_version,
        payload=payload,
        disposition="INVALID_CAPTURE",
        reason_code=reason_code,
        line_count=0,
        nonempty_line_count=0,
        observations=[],
    )


def _observation(
    *,
    sequence: int,
    line_number: int,
    document: str,
    start: int,
    end: int,
    surface: str,
    definition: str,
) -> dict[str, Any]:
    evidence = document[start:end]
    material: dict[str, Any] = {
        "schema_version": OBSERVATION_SCHEMA,
        "observation_sequence": sequence,
        "line_number": line_number,
        "relation_kind": "PRESENTED_EXPLICIT_DEFINITION_STATEMENT",
        "character_span_start": start,
        "character_span_end": end,
        "utf8_byte_span_start": len(document[:start].encode("utf-8")),
        "utf8_byte_span_end": len(document[:end].encode("utf-8")),
        "evidence_text": evidence,
        "evidence_utf8_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
        "surface_text": surface,
        "surface_utf8_sha256": hashlib.sha256(surface.encode("utf-8")).hexdigest(),
        "presented_definition_text": definition,
        "presented_definition_utf8_sha256": hashlib.sha256(
            definition.encode("utf-8")
        ).hexdigest(),
    }
    return {**material, "observation_sha256": _canonical_sha256(material)}


def _derive_expected(
    *,
    source_profile: str,
    content_type: str,
    capture_version: str,
    normalization_version: str,
    payload: bytes,
) -> dict[str, Any]:
    source_profile = _metadata(source_profile, "source_profile")
    content_type = _metadata(content_type, "content_type")
    capture_version = _metadata(capture_version, "capture_version")
    normalization_version = _metadata(
        normalization_version, "normalization_version"
    )
    if type(payload) is not bytes:
        raise P0RawCaptureCoreParentValidationError("payload must be exact bytes")

    if not payload:
        return _invalid(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            reason_code="empty_payload",
        )
    if len(payload) > MAX_PAYLOAD_BYTES:
        return _invalid(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            reason_code="payload_byte_limit_exceeded",
        )

    unsupported = _unsupported_reason(
        source_profile, content_type, capture_version, normalization_version
    )
    if unsupported is not None:
        return _result(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            disposition="UNSUPPORTED_PROFILE",
            reason_code=unsupported,
            line_count=0,
            nonempty_line_count=0,
            observations=[],
        )
    try:
        document = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return _invalid(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            reason_code="invalid_utf8",
        )

    invalid_reason = None
    if document.startswith("\ufeff"):
        invalid_reason = "utf8_bom_forbidden"
    elif "\x00" in document:
        invalid_reason = "nul_forbidden"
    elif "\r" in document:
        invalid_reason = "non_lf_line_ending"
    elif len(document) > MAX_DOCUMENT_CHARS:
        invalid_reason = "document_character_limit_exceeded"
    elif unicodedata.normalize("NFC", document) != document:
        invalid_reason = "document_not_nfc"
    elif any(char in _FORBIDDEN_INVISIBLE for char in document):
        invalid_reason = "invisible_format_character_forbidden"
    if invalid_reason is not None:
        return _invalid(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            reason_code=invalid_reason,
        )

    lines = document.split("\n")
    if document.endswith("\n"):
        lines = lines[:-1]
    nonempty = [(index, line) for index, line in enumerate(lines, start=1) if line]
    matched: list[tuple[int, str, str, str]] = []
    for line_number, line in nonempty:
        relation = None
        for pattern in _RELATIONS:
            relation = pattern.fullmatch(line)
            if relation is not None:
                break
        if relation is None:
            continue
        surface = relation.group("surface")
        definition = relation.group("presented_definition")
        if not _relation_text(surface, MAX_SURFACE_CHARS) or not _relation_text(
            definition, MAX_DEFINITION_CHARS
        ):
            continue
        matched.append((line_number, line, surface, definition))

    if not nonempty or len(matched) != len(nonempty):
        return _result(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            disposition="NO_MATCH",
            reason_code=(
                "no_nonempty_statement"
                if not nonempty
                else "mixed_or_nonmatching_context_fail_closed"
            ),
            line_count=len(lines),
            nonempty_line_count=len(nonempty),
            observations=[],
        )
    if len(matched) > MAX_OBSERVATIONS:
        return _invalid(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            reason_code="observation_limit_exceeded",
        )

    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line) + 1
    observations = [
        _observation(
            sequence=sequence,
            line_number=line_number,
            document=document,
            start=offsets[line_number - 1],
            end=offsets[line_number - 1] + len(line),
            surface=surface,
            definition=definition,
        )
        for sequence, (line_number, line, surface, definition) in enumerate(
            matched, start=1
        )
    ]
    return _result(
        source_profile=source_profile,
        content_type=content_type,
        capture_version=capture_version,
        normalization_version=normalization_version,
        payload=payload,
        disposition="MATCHED",
        reason_code="all_nonempty_lines_are_explicit_definition_observations",
        line_count=len(lines),
        nonempty_line_count=len(nonempty),
        observations=observations,
    )


def validate_result_against_capture(
    result: Mapping[str, Any],
    *,
    source_profile: str,
    content_type: str,
    capture_version: str,
    normalization_version: str,
    payload: bytes,
) -> dict[str, Any]:
    """Independently replay one capture and return a non-authority receipt."""

    if type(result) is not dict or set(result) != _RESULT_FIELDS:
        raise P0RawCaptureCoreParentValidationError("result field set mismatch")
    observations = result.get("observations")
    if not isinstance(observations, list):
        raise P0RawCaptureCoreParentValidationError("observations must be a list")
    for row in observations:
        if type(row) is not dict or set(row) != _OBSERVATION_FIELDS:
            raise P0RawCaptureCoreParentValidationError(
                "observation field set mismatch"
            )
    expected = _derive_expected(
        source_profile=source_profile,
        content_type=content_type,
        capture_version=capture_version,
        normalization_version=normalization_version,
        payload=payload,
    )
    try:
        presented_bytes = _canonical_bytes(dict(result))
    except (TypeError, ValueError) as exc:
        raise P0RawCaptureCoreParentValidationError(
            "presented result is not canonical JSON data"
        ) from exc
    if presented_bytes != _canonical_bytes(expected):
        raise P0RawCaptureCoreParentValidationError(
            "presented result differs from independent capture replay"
        )
    receipt_material: dict[str, Any] = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "core_version": EXPECTED_CORE_VERSION,
        "core_manifest_sha256": EXPECTED_CORE_MANIFEST_SHA256,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "result_sha256": result["result_sha256"],
        "disposition": result["disposition"],
        "observation_count": result["observation_count"],
        "parent_separate_implementation_capture_replay_verified": True,
        "neutral_observation_schema_verified": True,
        "same_process_isolation_verified": False,
        "core_code_identity_verified": False,
        "parent_code_identity_verified": False,
        "claim_rows_emitted": False,
        "target_ids_emitted": False,
        "route_or_credit_emitted": False,
        "capture_adapter_authority_verified": False,
        "parser_runtime_execution_verified": False,
        "dependency_closure_verified": False,
        "actual_semantic_evidence_verified": False,
        "actual_authority_granted": False,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "gate_status": GATE_STATUS,
    }
    return {
        **receipt_material,
        "receipt_sha256": _canonical_sha256(receipt_material),
    }


__all__ = [
    "EXPECTED_CORE_MANIFEST_SHA256",
    "EXPECTED_CORE_VERSION",
    "GATE_STATUS",
    "P0RawCaptureCoreParentValidationError",
    "VALIDATION_RECEIPT_SCHEMA",
    "validate_result_against_capture",
]
