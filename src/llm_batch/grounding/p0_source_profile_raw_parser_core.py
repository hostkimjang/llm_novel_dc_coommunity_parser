"""Pure neutral observation core for one bounded raw capture contract.

The core recognizes only a controlled ``COMMUNITY_STRUCTURED`` UTF-8 line-list
contract.  It emits neutral source spans, never claim/route/target/credit rows.
Official JSON/HTML, OCR transcripts, generic input, and unknown adapters remain
unsupported until an owner-pinned capture adapter and provenance contract exist.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping


RESULT_SCHEMA = "p0_raw_capture_neutral_observation_result_v1"
OBSERVATION_SCHEMA = "p0_raw_capture_neutral_observation_v1"
CORE_MANIFEST_SCHEMA = "p0_raw_capture_parser_core_manifest_v1"
CORE_VERSION = "raw-captured-utf8-neutral-observation-core-v1"

SUPPORTED_PROFILE = "COMMUNITY_STRUCTURED"
SUPPORTED_CONTENT_TYPE = "text/plain; charset=utf-8"
SUPPORTED_CAPTURE_VERSION = "normalized-community-explicit-statement-lines-v1"
SUPPORTED_NORMALIZATION_VERSION = "utf8_identity_v1"

KNOWN_PROFILES = (
    "OFFICIAL_STRUCTURED",
    "COMMUNITY_STRUCTURED",
    "MEDIA_OCR",
    "GENERIC_FALLBACK",
)
DISPOSITIONS = (
    "MATCHED",
    "NO_MATCH",
    "UNSUPPORTED_PROFILE",
    "INVALID_CAPTURE",
)

MAX_PAYLOAD_BYTES = 256 * 1024
MAX_DOCUMENT_CHARS = 64 * 1024
MAX_OBSERVATIONS = 64
MAX_SURFACE_CHARS = 512
MAX_DEFINITION_CHARS = 4096
MAX_METADATA_CHARS = 512

RELATION_GRAMMARS = (
    "'<surface>'은 <presented_definition_text>을 뜻한다.",
    "'<surface>'은 <presented_definition_text>를 뜻한다.",
    "'<surface>'는 <presented_definition_text>을 뜻한다.",
    "'<surface>'는 <presented_definition_text>를 뜻한다.",
)
RELATION_KIND = "PRESENTED_EXPLICIT_DEFINITION_STATEMENT"
_RELATIONS = (
    re.compile(
        r"^'(?P<surface>[^'\n]{1,512})'(?:은|는) "
        r"(?P<presented_definition>.+?)(?:을|를) 뜻한다\.$"
    ),
)
FORBIDDEN_DOCUMENT_FORMAT_CHARACTERS = ("\u200b", "\u200c", "\u200d", "\ufeff")
FORBIDDEN_RELATION_CHARACTERS = (
    "'", '"', "\\", ".", "?", "!", "。", "！", "？", "\u2026"
)
FORBIDDEN_RELATION_CATEGORIES = ("Cc", "Cf", "Cs", "Zl", "Zp")
REASON_CODES = (
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
_FORBIDDEN_INVISIBLE = frozenset(FORBIDDEN_DOCUMENT_FORMAT_CHARACTERS)
_FORBIDDEN_RELATION_CHARACTERS = frozenset(FORBIDDEN_RELATION_CHARACTERS)
_FORBIDDEN_RELATION_CATEGORIES = frozenset(FORBIDDEN_RELATION_CATEGORIES)

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


class P0RawCaptureParserCoreError(ValueError):
    """The direct core API was called with an invalid envelope value."""


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


CORE_MANIFEST: dict[str, Any] = {
    "schema_version": CORE_MANIFEST_SCHEMA,
    "core_version": CORE_VERSION,
    "result_schema": RESULT_SCHEMA,
    "observation_schema": OBSERVATION_SCHEMA,
    "supported_capture_contract": {
        "source_profile": SUPPORTED_PROFILE,
        "content_type": SUPPORTED_CONTENT_TYPE,
        "capture_version": SUPPORTED_CAPTURE_VERSION,
        "normalization_version": SUPPORTED_NORMALIZATION_VERSION,
    },
    "unsupported_profiles": [
        "OFFICIAL_STRUCTURED",
        "MEDIA_OCR",
        "GENERIC_FALLBACK",
    ],
    "relation_grammars": list(RELATION_GRAMMARS),
    "match_boundary_policy": "ALL_NONEMPTY_LINES_MUST_MATCH_WHOLE_LINE",
    "line_policy": "LF_ONLY_FINAL_LF_OPTIONAL_BLANK_LINES_ALLOWED",
    "dispositions": list(DISPOSITIONS),
    "reason_codes": list(REASON_CODES),
    "metadata_policy": {
        "max_chars": MAX_METADATA_CHARS,
        "nfc_required": True,
        "trimmed_nonempty_required": True,
        "forbidden_unicode_categories": list(FORBIDDEN_RELATION_CATEGORIES),
    },
    "relation_text_policy": {
        "forbidden_characters": list(FORBIDDEN_RELATION_CHARACTERS),
        "forbidden_unicode_categories": list(FORBIDDEN_RELATION_CATEGORIES),
    },
    "document_policy": {
        "forbidden_format_characters": list(
            FORBIDDEN_DOCUMENT_FORMAT_CHARACTERS
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
CORE_MANIFEST_SHA256 = canonical_sha256(CORE_MANIFEST)


def _canonical_metadata(value: Any, field: str) -> str:
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
        raise P0RawCaptureParserCoreError(f"{field} must be canonical text")
    return value


def _canonical_relation_text(value: str, *, maximum: int) -> bool:
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
    if source_profile != SUPPORTED_PROFILE:
        return "unknown_source_profile"
    if (
        content_type != SUPPORTED_CONTENT_TYPE
        or capture_version != SUPPORTED_CAPTURE_VERSION
        or normalization_version != SUPPORTED_NORMALIZATION_VERSION
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
        "core_version": CORE_VERSION,
        "core_manifest_sha256": CORE_MANIFEST_SHA256,
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
        "observations_sha256": canonical_sha256(observations),
    }
    result = {**material, "result_sha256": canonical_sha256(material)}
    if set(result) != _RESULT_FIELDS:
        raise AssertionError("raw parser result field drift")
    return result


def _invalid_capture_result(
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
        "relation_kind": RELATION_KIND,
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
    row = {**material, "observation_sha256": canonical_sha256(material)}
    if set(row) != _OBSERVATION_FIELDS:
        raise AssertionError("raw parser observation field drift")
    return row


def parse_capture(
    *,
    source_profile: str,
    content_type: str,
    capture_version: str,
    normalization_version: str,
    payload: bytes,
) -> dict[str, Any]:
    """Parse exact captured bytes into neutral, non-authoritative observations."""

    source_profile = _canonical_metadata(source_profile, "source_profile")
    content_type = _canonical_metadata(content_type, "content_type")
    capture_version = _canonical_metadata(capture_version, "capture_version")
    normalization_version = _canonical_metadata(
        normalization_version, "normalization_version"
    )
    if type(payload) is not bytes:
        raise P0RawCaptureParserCoreError("payload must be exact bytes")

    if not payload:
        return _invalid_capture_result(
            source_profile=source_profile,
            content_type=content_type,
            capture_version=capture_version,
            normalization_version=normalization_version,
            payload=payload,
            reason_code="empty_payload",
        )
    if len(payload) > MAX_PAYLOAD_BYTES:
        return _invalid_capture_result(
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
        return _invalid_capture_result(
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
        return _invalid_capture_result(
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
        if not _canonical_relation_text(
            surface, maximum=MAX_SURFACE_CHARS
        ) or not _canonical_relation_text(definition, maximum=MAX_DEFINITION_CHARS):
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
        return _invalid_capture_result(
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


__all__ = [
    "CORE_MANIFEST",
    "CORE_MANIFEST_SHA256",
    "CORE_VERSION",
    "DISPOSITIONS",
    "KNOWN_PROFILES",
    "OBSERVATION_SCHEMA",
    "P0RawCaptureParserCoreError",
    "RESULT_SCHEMA",
    "SUPPORTED_CAPTURE_VERSION",
    "SUPPORTED_CONTENT_TYPE",
    "SUPPORTED_NORMALIZATION_VERSION",
    "SUPPORTED_PROFILE",
    "canonical_bytes",
    "canonical_sha256",
    "parse_capture",
]
