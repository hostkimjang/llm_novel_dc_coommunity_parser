"""Additive presented-only separation of HTTP transport time and page revision.

V1 called a value derived from ``Date`` or ``Last-Modified`` a source
timestamp.  This successor does not reinterpret or mutate that wire format.
It validates the exact V1 inputs, classifies both HTTP headers as transport or
representation metadata only, and accepts page-native revision evidence only
when the caller supplies an exact span in the decoded response entity.

No network, filesystem, clock, parser, authority, credit, metric, publication,
or production capability is granted by this component.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from . import p0_presented_http_capture_intake_v1_contract as capture_v1


ROW_SCHEMA = "p0_presented_http_capture_temporal_evidence_row_v2"
BUNDLE_SCHEMA = "p0_presented_http_capture_temporal_evidence_bundle_v2"
RECEIPT_SCHEMA = "p0_presented_http_capture_temporal_evidence_receipt_v2"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_http_capture_temporal_evidence_component_manifest_v2"
COMPONENT_VERSION = "presented-http-capture-temporal-evidence-v2"
RECORD_ORIGIN = "PRESENTED_UNVERIFIED"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_TEMPORAL_EVIDENCE_ONLY"
METRIC_STATUS = "NOT_ESTIMABLE"

EXPECTED_SEED_COUNT = 8
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_PAGE_REVISION_VALUE_CHARS = 128
MAX_PAGE_REVISION_SIGNALS = 3
MAX_PAGE_REVISION_EVIDENCE_BYTES = 512
PREDECESSOR_COMPONENT_MANIFEST_SHA256 = (
    "e115cd8c8da2b7f4b09c0ff252055656ac206da062afc0fb9edbc517a8a77339"
)

PAGE_REVISION_STATUSES = (
    "NOT_EXPOSED",
    "PRESENTED_LOCATED",
)
PAGE_REVISION_KINDS = (
    "NONE",
    "PUBLISHED_AT",
    "MODIFIED_AT",
    "VERSION_ID",
)
PAGE_REVISION_VALUE_TYPES = (
    "NONE",
    "PRESENTED_TIMESTAMP_TEXT",
    "OPAQUE_VERSION_TOKEN",
)
PAGE_REVISION_SYNTAXES = (
    "JSON_LD_DATE_PUBLISHED",
    "JSON_LD_DATE_MODIFIED",
    "OPEN_GRAPH_ARTICLE_PUBLISHED_TIME",
    "OPEN_GRAPH_ARTICLE_MODIFIED_TIME",
    "SITE_NATIVE_VERSION_TOKEN",
)

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_UTC_RFC3339_RE = re.compile(
    r"^(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_PRESENTED_RFC3339_RE = re.compile(
    r"^(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:Z|[+-][0-2][0-9]:[0-5][0-9])$"
)
_VERSION_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

_FALSE_CAPABILITIES = (
    "transport_time_authority_verified",
    "page_revision_authority_verified",
    "page_revision_parser_verified",
    "capture_authority_verified",
    "rights_authority_verified",
    "retention_authority_verified",
    "source_attestation_verified",
    "actual_source_snapshot_credited",
    "claim_derivation_allowed",
    "derived_index_allowed",
    "publication_evidence_allowed",
    "metric_denominator_eligible",
    "actual_authority_granted",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
    "action_applied",
)
_PAGE_INPUT_FIELDS = frozenset({
    "seed_sequence", "seed_id", "capture_row_sha256",
    "native_revision_status", "signals", "record_sha256",
})
_SIGNAL_INPUT_FIELDS = frozenset({
    "kind", "syntax", "context_start", "context_end", "value_start",
    "value_end", "context_sha256", "value_sha256", "presented_value",
    "normalized_value",
})
_SIGNAL_OUTPUT_FIELDS = frozenset({
    "kind", "syntax", "context_start", "context_end", "value_start",
    "value_end", "context_sha256", "value_sha256", "normalized_value",
    "signal_sha256",
})
_TRANSPORT_FIELDS = frozenset({
    "presented_collected_at", "clock_source",
    "clock_attestation_ref_sha256", "http_date_header",
    "http_date_instant", "http_date_role", "http_last_modified_header",
    "http_last_modified_instant", "http_last_modified_role",
    "legacy_source_timestamp", "legacy_source_timestamp_basis",
    "legacy_source_timestamp_role", "transport_observation_sha256",
})
_PAGE_PROJECTION_FIELDS = frozenset({
    "native_revision_status", "signal_count", "signals",
    "revision_observation_identity_sha256", "presented_record_sha256",
    "page_revision_projection_sha256",
})
_ROW_FIELDS = frozenset({
    "schema_version", "record_origin", "seed_sequence", "seed_id",
    "source_id", "track", "source_lineage", "final_url",
    "predecessor_row_sha256", "raw_response_bytes", "raw_response_sha256",
    "transport_observation", "page_native_revision_evidence",
    "transport_and_page_revision_separated",
    "http_headers_accepted_as_page_revision", *_FALSE_CAPABILITIES,
    "operational_effect", "row_sha256",
})
_BUNDLE_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version",
    "component_manifest_sha256", "predecessor_component_manifest_sha256",
    "predecessor_intake_raw_sha256", "predecessor_receipt_raw_sha256",
    "rows", "row_count", "track_counts", "rows_sha256",
    "page_revision_presented_count", "page_revision_not_exposed_count",
    "page_revision_signal_count", "revision_observation_identities_sha256",
    "replay_idempotency_key_sha256",
    "http_date_present_count", "http_last_modified_present_count",
    "http_header_page_revision_promotion_count", "raw_payload_exposed",
    "credited_actual_source_snapshot_count", "metric_denominator",
    "metric_status", *_FALSE_CAPABILITIES, "operational_effect",
    "gate_status", "blockers", "artifact_sha256",
})
_RECEIPT_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version",
    "component_manifest_sha256", "predecessor_component_manifest_sha256",
    "predecessor_intake_raw_sha256", "predecessor_receipt_raw_sha256",
    "temporal_artifact_raw_sha256", "temporal_artifact_sha256",
    "row_count", "rows_sha256", "page_revision_presented_count",
    "page_revision_not_exposed_count", "http_date_present_count",
    "page_revision_signal_count", "revision_observation_identities_sha256",
    "replay_idempotency_key_sha256",
    "http_last_modified_present_count",
    "transport_page_revision_separation_verified",
    "all_presented_page_revision_spans_verified",
    "http_header_page_revision_promotion_count", "raw_payload_exposed",
    "actual_credit_count", "metric_denominator", "metric_status",
    *_FALSE_CAPABILITIES, "operational_effect", "gate_status", "blockers",
    "receipt_sha256",
})


class P0PresentedHttpCaptureTemporalEvidenceV2Error(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "canonical JSON invalid"
        ) from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "raw input must be exact bytes"
        )
    return hashlib.sha256(raw).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
        f"non-finite JSON constant: {value}"
    )


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes or not raw or len(raw) > MAX_ARTIFACT_BYTES
        or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{label} framing invalid"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                f"{label} must be NFC"
            )
        value = json.loads(
            text, object_pairs_hook=_pairs, parse_constant=_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        if isinstance(exc, P0PresentedHttpCaptureTemporalEvidenceV2Error):
            raise
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{label} parse invalid"
        ) from exc
    if type(value) is not dict or raw != canonical_file_bytes(value):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{label} canonical bytes mismatch"
        )
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{label} fields mismatch"
        )
    return dict(value)


def _text(value: Any, field: str, maximum: int = 256) -> str:
    if (
        type(value) is not str or not value or value != value.strip()
        or len(value) > maximum or unicodedata.normalize("NFC", value) != value
        or any(ord(char) < 0x20 or unicodedata.category(char) in {"Cf", "Cs"} for char in value)
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} text invalid"
        )
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if _ID_RE.fullmatch(text) is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} identifier invalid"
        )
    return text


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} SHA-256 invalid"
        )
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} integer invalid"
        )
    return value


def _utc_timestamp(value: Any, field: str) -> str:
    text = _text(value, field, 32)
    if _UTC_RFC3339_RE.fullmatch(text) is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} must be canonical UTC RFC3339 seconds"
        )
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} timestamp invalid"
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} UTC timestamp invalid"
        )
    return text


def _normalize_presented_timestamp(value: str, field: str) -> str:
    if value.endswith("-00:00") or _PRESENTED_RFC3339_RE.fullmatch(value) is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} presented timestamp syntax invalid"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} presented timestamp invalid"
        ) from exc
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_instant(value: Any, field: str) -> str | None:
    if value is None:
        return None
    text = _text(value, field, 128)
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError) as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} HTTP date invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            f"{field} timezone missing"
        )
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_predecessor(
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
    intake_raw: bytes,
    intake_receipt_raw: bytes,
) -> dict[str, Any]:
    if capture_v1.COMPONENT_MANIFEST_SHA256 != PREDECESSOR_COMPONENT_MANIFEST_SHA256:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "predecessor component identity mismatch"
        )
    try:
        intake = capture_v1.validate_intake_bytes(
            intake_raw,
            seed_registry_raw=seed_registry_raw,
            presented_records=presented_records,
            raw_payloads_by_seed=raw_payloads_by_seed,
        )
        capture_v1.validate_receipt_bytes(
            intake_receipt_raw,
            intake_raw=intake_raw,
            seed_registry_raw=seed_registry_raw,
            presented_records=presented_records,
            raw_payloads_by_seed=raw_payloads_by_seed,
        )
    except Exception as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "predecessor capture replay failed"
        ) from exc
    if (
        intake.get("component_manifest_sha256")
        != PREDECESSOR_COMPONENT_MANIFEST_SHA256
        or intake.get("row_count") != EXPECTED_SEED_COUNT
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "predecessor capture identity mismatch"
        )
    return intake


def _transport(row: Mapping[str, Any]) -> dict[str, Any]:
    timing = row["capture_timing_provenance"]
    timestamps = row["source_timestamp_evidence"]
    date_header = timestamps["date_header"]
    modified_header = timestamps["last_modified_header"]
    date_instant = _http_instant(date_header, "HTTP Date")
    modified_instant = _http_instant(modified_header, "HTTP Last-Modified")
    capture_instant = _normalize_presented_timestamp(
        timing["presented_collected_at"], "presented_collected_at"
    )
    if (
        date_instant is not None and modified_instant is not None
        and modified_instant > date_instant
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "HTTP Last-Modified cannot follow HTTP Date"
        )
    if any(
        instant is not None and instant > capture_instant
        for instant in (date_instant, modified_instant)
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "HTTP metadata cannot follow capture observation"
        )
    material = {
        "presented_collected_at": timing["presented_collected_at"],
        "clock_source": timing["clock_source"],
        "clock_attestation_ref_sha256": timing["clock_attestation_ref_sha256"],
        "http_date_header": date_header,
        "http_date_instant": date_instant,
        "http_date_role": (
            "HTTP_RESPONSE_ORIGIN_DATE_NOT_PAGE_REVISION"
            if date_header is not None else "NOT_EXPOSED"
        ),
        "http_last_modified_header": modified_header,
        "http_last_modified_instant": modified_instant,
        "http_last_modified_role": (
            "HTTP_REPRESENTATION_METADATA_NOT_PAGE_NATIVE_REVISION"
            if modified_header is not None else "NOT_EXPOSED"
        ),
        "legacy_source_timestamp": timestamps["source_timestamp"],
        "legacy_source_timestamp_basis": timestamps["source_timestamp_basis"],
        "legacy_source_timestamp_role": (
            "LEGACY_HTTP_METADATA_ONLY_NOT_PAGE_NATIVE_REVISION"
            if timestamps["source_timestamp_basis"] != "NOT_EXPOSED"
            else "NOT_EXPOSED"
        ),
    }
    return with_self_hash(material, "transport_observation_sha256")


def _page_projection(
    value: Any,
    *,
    expected_sequence: int,
    expected_seed_id: str,
    expected_capture_row_sha256: str,
    capture_observed_at: str,
    payload: bytes,
) -> dict[str, Any]:
    row = _strict(value, _PAGE_INPUT_FIELDS, "page-native revision record")
    if (
        _integer(row["seed_sequence"], "seed_sequence", 1) != expected_sequence
        or _identifier(row["seed_id"], "seed_id") != expected_seed_id
        or _sha(row["capture_row_sha256"], "capture_row_sha256")
        != expected_capture_row_sha256
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "page revision/seed binding mismatch"
        )
    if (
        type(row["signals"]) is not list
        or len(row["signals"]) > MAX_PAGE_REVISION_SIGNALS
        or any(type(item) is not dict for item in row["signals"])
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "page revision signals must be exact objects"
        )
    _sha(row["record_sha256"], "page revision record SHA")
    _text(row["native_revision_status"], "native_revision_status", 32)
    for index, raw_signal in enumerate(row["signals"], start=1):
        signal = _strict(
            raw_signal, _SIGNAL_INPUT_FIELDS,
            f"page revision signal {index} preflight",
        )
        _text(signal["kind"], "kind", 32)
        _text(signal["syntax"], "syntax", 64)
        _text(
            signal["presented_value"], "presented_value",
            MAX_PAGE_REVISION_VALUE_CHARS,
        )
        _text(
            signal["normalized_value"], "normalized_value",
            MAX_PAGE_REVISION_VALUE_CHARS,
        )
        _sha(signal["context_sha256"], "context_sha256")
        _sha(signal["value_sha256"], "value_sha256")
        context_start = _integer(signal["context_start"], "context_start", 0)
        context_end = _integer(signal["context_end"], "context_end", 1)
        value_start = _integer(signal["value_start"], "value_start", 0)
        value_end = _integer(signal["value_end"], "value_end", 1)
        if (
            context_start >= context_end or context_end > len(payload)
            or value_start >= value_end or value_end > len(payload)
            or not (context_start <= value_start < value_end <= context_end)
            or context_end - context_start > MAX_PAGE_REVISION_EVIDENCE_BYTES
            or value_end - value_start > MAX_PAGE_REVISION_VALUE_CHARS * 4
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision locator preflight invalid"
            )
    material = dict(row)
    supplied_hash = _sha(material.pop("record_sha256"), "page revision record SHA")
    material["signals"] = sorted(
        material["signals"], key=lambda item: str(item.get("kind", ""))
    )
    if supplied_hash != canonical_sha256(material):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "page revision record hash mismatch"
        )
    status = row["native_revision_status"]
    if status not in PAGE_REVISION_STATUSES:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "page revision classification invalid"
        )
    if status == "NOT_EXPOSED":
        if row["signals"]:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "NOT_EXPOSED page revision must have no signals"
            )
        projection = {
            "native_revision_status": status, "signal_count": 0,
            "signals": [],
            "revision_observation_identity_sha256": None,
            "presented_record_sha256": supplied_hash,
        }
        return with_self_hash(projection, "page_revision_projection_sha256")
    if not row["signals"] or len(row["signals"]) > MAX_PAGE_REVISION_SIGNALS:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "presented page revision signal count invalid"
        )
    kind_order = {kind: index for index, kind in enumerate(PAGE_REVISION_KINDS)}
    output_signals: list[dict[str, Any]] = []
    seen_kinds: set[str] = set()
    seen_value_spans: list[tuple[int, int]] = []
    for index, raw_signal in enumerate(row["signals"], start=1):
        signal = _strict(
            raw_signal, _SIGNAL_INPUT_FIELDS, f"page revision signal {index}"
        )
        kind = signal["kind"]
        syntax = signal["syntax"]
        if kind not in {"PUBLISHED_AT", "MODIFIED_AT", "VERSION_ID"} or kind in seen_kinds:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision signal kind invalid or duplicate"
            )
        allowed_syntaxes = {
            "PUBLISHED_AT": {
                "JSON_LD_DATE_PUBLISHED", "OPEN_GRAPH_ARTICLE_PUBLISHED_TIME",
            },
            "MODIFIED_AT": {
                "JSON_LD_DATE_MODIFIED", "OPEN_GRAPH_ARTICLE_MODIFIED_TIME",
            },
            "VERSION_ID": {"SITE_NATIVE_VERSION_TOKEN"},
        }[kind]
        if syntax not in allowed_syntaxes:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision kind/syntax mismatch"
            )
        context_start = _integer(signal["context_start"], "context_start", 0)
        context_end = _integer(signal["context_end"], "context_end", 1)
        value_start = _integer(signal["value_start"], "value_start", 0)
        value_end = _integer(signal["value_end"], "value_end", 1)
        if (
            context_start >= context_end or context_end > len(payload)
            or context_end - context_start > MAX_PAGE_REVISION_EVIDENCE_BYTES
            or not (context_start <= value_start < value_end <= context_end)
            or value_end - value_start > MAX_PAGE_REVISION_VALUE_CHARS * 4
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision locator invalid"
            )
        if any(
            not (value_end <= prior_start or value_start >= prior_end)
            for prior_start, prior_end in seen_value_spans
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision value span role overlap"
            )
        context = payload[context_start:context_end]
        evidence = payload[value_start:value_end]
        if (
            _sha(signal["context_sha256"], "context_sha256") != raw_sha256(context)
            or _sha(signal["value_sha256"], "value_sha256") != raw_sha256(evidence)
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision locator hash mismatch"
            )
        try:
            presented_value = evidence.decode("utf-8", errors="strict")
            context.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision locator must be UTF-8"
            ) from exc
        if presented_value != _text(
            signal["presented_value"], "presented_value",
            MAX_PAGE_REVISION_VALUE_CHARS,
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision value/span mismatch"
            )
        context_text = context.decode("utf-8", errors="strict").strip()
        if syntax.startswith("JSON_LD_"):
            try:
                context_object = json.loads(
                    context_text, object_pairs_hook=_pairs,
                    parse_constant=_constant,
                )
            except (json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
                if isinstance(exc, P0PresentedHttpCaptureTemporalEvidenceV2Error):
                    raise
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "JSON-LD page revision context invalid"
                ) from exc
            field_name = (
                "datePublished" if kind == "PUBLISHED_AT" else "dateModified"
            )
            if (
                type(context_object) is not dict
                or context_object.get(field_name) != presented_value
                or any(type(item) in {dict, list} for item in context_object.values())
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "JSON-LD page revision marker/value mismatch"
                )
            relative_value_span = (
                value_start - context_start, value_end - context_start
            )
            marker_pattern = (
                rb'"' + field_name.encode("ascii") + rb'"\s*:\s*"('
                + re.escape(evidence) + rb')"'
            )
            if not any(
                match.span(1) == relative_value_span
                for match in re.finditer(marker_pattern, context)
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "JSON-LD marker/value locator mismatch"
                )
        elif syntax.startswith("OPEN_GRAPH_"):
            property_name = (
                "article:published_time"
                if kind == "PUBLISHED_AT" else "article:modified_time"
            )
            escaped_property = re.escape(property_name)
            escaped_value = re.escape(presented_value)
            patterns = (
                rf'<meta property="{escaped_property}" content="{escaped_value}"\s*/?>',
                rf'<meta content="{escaped_value}" property="{escaped_property}"\s*/?>',
            )
            if not any(re.fullmatch(pattern, context_text) for pattern in patterns):
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "Open Graph page revision marker/value mismatch"
                )
            content_marker = b'content="' + evidence + b'"'
            marker_start = context.find(content_marker)
            if (
                marker_start < 0
                or marker_start + len(b'content="')
                != value_start - context_start
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "Open Graph marker/value locator mismatch"
                )
        else:
            version_pattern = (
                rb'(?:^|[\t\n\r\f ])data-version="('
                + re.escape(evidence) + rb')"(?=$|[\t\n\r\f />])'
            )
            relative_value_span = (
                value_start - context_start, value_end - context_start
            )
            marker_locator_verified = False
            for match in re.finditer(version_pattern, context):
                if match.span(1) != relative_value_span:
                    continue
                absolute_marker_start = (
                    context_start + match.start(1) - len(b'data-version="')
                )
                absolute_marker_end = context_start + match.end(1) + 1
                left_ok = (
                    absolute_marker_start == 0
                    or payload[absolute_marker_start - 1] in b"\t\n\r\f "
                )
                right_ok = (
                    absolute_marker_end == len(payload)
                    or payload[absolute_marker_end] in b"\t\n\r\f />"
                )
                if left_ok and right_ok:
                    marker_locator_verified = True
                    break
            if not marker_locator_verified:
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "site-native version marker/value locator mismatch"
                )
        normalized_value = _text(
            signal["normalized_value"], "normalized_value",
            MAX_PAGE_REVISION_VALUE_CHARS,
        )
        if kind in {"PUBLISHED_AT", "MODIFIED_AT"}:
            if normalized_value != _normalize_presented_timestamp(
                presented_value, "presented_value"
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "page revision timestamp normalization mismatch"
                )
        elif (
            not presented_value.isascii()
            or _VERSION_TOKEN_RE.fullmatch(presented_value) is None
            or normalized_value != presented_value
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision version token invalid"
            )
        output_signal = with_self_hash({
            "kind": kind, "syntax": syntax,
            "context_start": context_start, "context_end": context_end,
            "value_start": value_start, "value_end": value_end,
            "context_sha256": raw_sha256(context),
            "value_sha256": raw_sha256(evidence),
            "normalized_value": normalized_value,
        }, "signal_sha256")
        if set(output_signal) != _SIGNAL_OUTPUT_FIELDS:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "page revision signal projection fields mismatch"
            )
        output_signals.append(output_signal)
        seen_kinds.add(kind)
        seen_value_spans.append((value_start, value_end))
    output_signals.sort(key=lambda item: kind_order[item["kind"]])
    signals_by_kind = {item["kind"]: item for item in output_signals}
    if (
        "PUBLISHED_AT" in signals_by_kind and "MODIFIED_AT" in signals_by_kind
        and signals_by_kind["PUBLISHED_AT"]["normalized_value"]
        > signals_by_kind["MODIFIED_AT"]["normalized_value"]
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "page revision chronology invalid"
        )
    try:
        observed = datetime.fromisoformat(capture_observed_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "capture observed timestamp invalid"
        ) from exc
    if observed.tzinfo is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "capture observed timestamp timezone missing"
        )
    observed_utc = observed.astimezone(timezone.utc)
    for item in output_signals:
        if item["kind"] in {"PUBLISHED_AT", "MODIFIED_AT"}:
            page_instant = datetime.fromisoformat(
                item["normalized_value"].replace("Z", "+00:00")
            )
            if page_instant > observed_utc:
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "page revision follows capture observation"
                )
    identity_material = {
        "domain": "p0-page-native-revision-identity-v2",
        "capture_row_sha256": expected_capture_row_sha256,
        "signals": output_signals,
    }
    projection = {
        "native_revision_status": status,
        "signal_count": len(output_signals), "signals": output_signals,
        "revision_observation_identity_sha256": canonical_sha256(identity_material),
        "presented_record_sha256": supplied_hash,
    }
    return with_self_hash(projection, "page_revision_projection_sha256")


COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component_version": COMPONENT_VERSION,
    "record_origin": RECORD_ORIGIN,
    "predecessor_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
    "expected_seed_count": EXPECTED_SEED_COUNT,
    "page_revision_statuses": list(PAGE_REVISION_STATUSES),
    "page_revision_kinds": list(PAGE_REVISION_KINDS),
    "page_revision_value_types": list(PAGE_REVISION_VALUE_TYPES),
    "page_revision_syntaxes": list(PAGE_REVISION_SYNTAXES),
    "http_date_semantics": "HTTP_RESPONSE_ORIGIN_DATE_NOT_PAGE_REVISION",
    "http_last_modified_semantics": "HTTP_REPRESENTATION_METADATA_NOT_PAGE_NATIVE_REVISION",
    "page_revision_evidence_basis": "EXACT_UTF8_SPAN_IN_DECODED_RESPONSE_ENTITY",
    "page_revision_timestamp_normalization": "CALLER_PRESENTED_UNVERIFIED_CANONICAL_UTC_RFC3339_SECONDS",
    "page_revision_raw_context_or_unnormalized_span_exposed_in_artifact": False,
    "page_revision_normalized_scalar_exposed_in_artifact": True,
    "revision_observation_identity_semantics": "CAPTURE_AND_LOCATOR_BOUND_NOT_A_STABLE_PAGE_REVISION_OR_LINEAGE_KEY",
    "replay_idempotency_semantics": "PURE_DETERMINISTIC_REPLAY_KEY_NOT_EXTERNAL_ANTI_REPLAY_OR_EFFECT_DEDUPLICATION",
    "max_page_revision_value_chars": MAX_PAGE_REVISION_VALUE_CHARS,
    "max_page_revision_signals": MAX_PAGE_REVISION_SIGNALS,
    "max_page_revision_evidence_bytes": MAX_PAGE_REVISION_EVIDENCE_BYTES,
    "network_access_allowed": False,
    "filesystem_access_allowed": False,
    "clock_access_allowed": False,
    "parser_execution_allowed": False,
    "actual_credit_allowed": False,
    "publication_evidence_allowed": False,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


def _rows(
    *,
    intake: Mapping[str, Any],
    raw_payloads_by_seed: Mapping[str, bytes],
    page_revision_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    predecessor_rows = intake["rows"]
    if type(page_revision_records) not in {list, tuple} or len(page_revision_records) != EXPECTED_SEED_COUNT:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "page revision records require exact seed count"
        )
    expected_ids = [row["seed_id"] for row in predecessor_rows]
    if type(raw_payloads_by_seed) is not dict or list(raw_payloads_by_seed) != expected_ids:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "payload mapping requires exact ordered seed IDs"
        )
    output: list[dict[str, Any]] = []
    for index, predecessor_row in enumerate(predecessor_rows):
        seed_id = predecessor_row["seed_id"]
        page = _page_projection(
            page_revision_records[index], expected_sequence=index + 1,
            expected_seed_id=seed_id,
            expected_capture_row_sha256=predecessor_row["row_sha256"],
            capture_observed_at=predecessor_row["capture_timing_provenance"]["presented_collected_at"],
            payload=raw_payloads_by_seed[seed_id],
        )
        material = {
            "schema_version": ROW_SCHEMA, "record_origin": RECORD_ORIGIN,
            "seed_sequence": index + 1, "seed_id": seed_id,
            "source_id": predecessor_row["source_id"],
            "track": predecessor_row["track"],
            "source_lineage": predecessor_row["source_lineage"],
            "final_url": predecessor_row["final_url"],
            "predecessor_row_sha256": predecessor_row["row_sha256"],
            "raw_response_bytes": predecessor_row["raw_response_bytes"],
            "raw_response_sha256": predecessor_row["raw_response_sha256"],
            "transport_observation": _transport(predecessor_row),
            "page_native_revision_evidence": page,
            "transport_and_page_revision_separated": True,
            "http_headers_accepted_as_page_revision": False,
            **{field: False for field in _FALSE_CAPABILITIES},
            "operational_effect": OPERATIONAL_EFFECT,
        }
        output.append(with_self_hash(material, "row_sha256"))
    return output


def _bundle_value(
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
    intake_raw: bytes,
    intake_receipt_raw: bytes,
    page_revision_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    intake = _validate_predecessor(
        seed_registry_raw=seed_registry_raw,
        presented_records=presented_records,
        raw_payloads_by_seed=raw_payloads_by_seed,
        intake_raw=intake_raw,
        intake_receipt_raw=intake_receipt_raw,
    )
    rows = _rows(
        intake=intake, raw_payloads_by_seed=raw_payloads_by_seed,
        page_revision_records=page_revision_records,
    )
    presented_count = sum(
        row["page_native_revision_evidence"]["native_revision_status"]
        == "PRESENTED_LOCATED" for row in rows
    )
    signal_count = sum(
        row["page_native_revision_evidence"]["signal_count"] for row in rows
    )
    replay_idempotency_key = canonical_sha256({
        "domain": "p0-presented-http-capture-temporal-evidence-v2-replay-idempotency",
        "predecessor_intake_raw_sha256": raw_sha256(intake_raw),
        "predecessor_receipt_raw_sha256": raw_sha256(intake_receipt_raw),
        "presented_page_revision_record_sha256s": [
            row["page_native_revision_evidence"]["presented_record_sha256"]
            for row in rows
        ],
    })
    material = {
        "schema_version": BUNDLE_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "predecessor_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
        "predecessor_intake_raw_sha256": raw_sha256(intake_raw),
        "predecessor_receipt_raw_sha256": raw_sha256(intake_receipt_raw),
        "rows": rows, "row_count": len(rows),
        "track_counts": dict(sorted(Counter(row["track"] for row in rows).items())),
        "rows_sha256": canonical_sha256(rows),
        "page_revision_presented_count": presented_count,
        "page_revision_not_exposed_count": len(rows) - presented_count,
        "page_revision_signal_count": signal_count,
        "revision_observation_identities_sha256": canonical_sha256([
            row["page_native_revision_evidence"]["revision_observation_identity_sha256"]
            for row in rows
        ]),
        "replay_idempotency_key_sha256": replay_idempotency_key,
        "http_date_present_count": sum(
            row["transport_observation"]["http_date_header"] is not None for row in rows
        ),
        "http_last_modified_present_count": sum(
            row["transport_observation"]["http_last_modified_header"] is not None for row in rows
        ),
        "http_header_page_revision_promotion_count": 0,
        "raw_payload_exposed": False,
        "credited_actual_source_snapshot_count": 0,
        "metric_denominator": 0, "metric_status": METRIC_STATUS,
        **{field: False for field in _FALSE_CAPABILITIES},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
        "blockers": [
            "ACTUAL_CAPTURE_AUTHORITY_NOT_VERIFIED",
            "PAGE_NATIVE_REVISION_PARSER_NOT_VERIFIED",
            "PAGE_REVISION_EVIDENCE_PRESENTED_ONLY",
            "RETENTION_ATTESTATION_NOT_VERIFIED",
            "RIGHTS_ATTESTATION_NOT_VERIFIED",
            "TRANSPORT_CLOCK_AUTHORITY_NOT_VERIFIED",
        ],
    }
    return with_self_hash(material, "artifact_sha256")


def _build_artifact_bytes_impl(**kwargs: Any) -> bytes:
    raw = canonical_file_bytes(_bundle_value(**kwargs))
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "temporal artifact exceeds byte limit"
        )
    return raw


def _validate_artifact_bytes_impl(raw: bytes, **kwargs: Any) -> dict[str, Any]:
    value = _strict(_object(raw, "temporal artifact"), _BUNDLE_FIELDS, "temporal artifact")
    expected = _bundle_value(**kwargs)
    if value != expected:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "temporal artifact replay mismatch"
        )
    return value


def _receipt_value(artifact_raw: bytes, **kwargs: Any) -> dict[str, Any]:
    artifact = _strict(
        _object(artifact_raw, "temporal artifact"), _BUNDLE_FIELDS,
        "temporal artifact",
    )
    expected = _bundle_value(**kwargs)
    if artifact != expected:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "temporal artifact replay mismatch"
        )
    material = {
        "schema_version": RECEIPT_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "predecessor_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
        "predecessor_intake_raw_sha256": artifact["predecessor_intake_raw_sha256"],
        "predecessor_receipt_raw_sha256": artifact["predecessor_receipt_raw_sha256"],
        "temporal_artifact_raw_sha256": raw_sha256(artifact_raw),
        "temporal_artifact_sha256": artifact["artifact_sha256"],
        "row_count": artifact["row_count"], "rows_sha256": artifact["rows_sha256"],
        "page_revision_presented_count": artifact["page_revision_presented_count"],
        "page_revision_not_exposed_count": artifact["page_revision_not_exposed_count"],
        "page_revision_signal_count": artifact["page_revision_signal_count"],
        "revision_observation_identities_sha256": artifact["revision_observation_identities_sha256"],
        "replay_idempotency_key_sha256": artifact["replay_idempotency_key_sha256"],
        "http_date_present_count": artifact["http_date_present_count"],
        "http_last_modified_present_count": artifact["http_last_modified_present_count"],
        "transport_page_revision_separation_verified": True,
        "all_presented_page_revision_spans_verified": True,
        "http_header_page_revision_promotion_count": 0,
        "raw_payload_exposed": False, "actual_credit_count": 0,
        "metric_denominator": 0, "metric_status": METRIC_STATUS,
        **{field: False for field in _FALSE_CAPABILITIES},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
        "blockers": artifact["blockers"],
    }
    return with_self_hash(material, "receipt_sha256")


def _build_receipt_bytes_impl(artifact_raw: bytes, **kwargs: Any) -> bytes:
    raw = canonical_file_bytes(_receipt_value(artifact_raw, **kwargs))
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "temporal receipt exceeds byte limit"
        )
    return raw


def _validate_receipt_bytes_impl(
    raw: bytes, *, artifact_raw: bytes, **kwargs: Any
) -> dict[str, Any]:
    value = _strict(_object(raw, "temporal receipt"), _RECEIPT_FIELDS, "temporal receipt")
    expected = _receipt_value(artifact_raw, **kwargs)
    if value != expected:
        raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
            "temporal receipt replay mismatch"
        )
    return value


def _make_runtime_integrity_guard():
    module_globals = globals()
    function_names = (
        "canonical_bytes", "canonical_file_bytes", "canonical_sha256",
        "raw_sha256", "with_self_hash", "_pairs", "_constant", "_object",
        "_strict", "_text", "_identifier", "_sha", "_integer",
        "_utc_timestamp", "_normalize_presented_timestamp", "_http_instant",
        "_validate_predecessor",
        "_transport", "_page_projection", "_rows", "_bundle_value",
        "_build_artifact_bytes_impl", "_validate_artifact_bytes_impl",
        "_receipt_value", "_build_receipt_bytes_impl",
        "_validate_receipt_bytes_impl",
    )
    expected_functions = tuple(
        (
            name, module_globals[name], module_globals[name].__code__,
            module_globals[name].__defaults__,
            tuple(sorted((module_globals[name].__kwdefaults__ or {}).items())),
        )
        for name in function_names
    )
    expected_capture_module = capture_v1
    expected_capture_entrypoints = (
        capture_v1.validate_intake_bytes, capture_v1.validate_receipt_bytes,
    )
    expected_external_functions = tuple(
        (
            function, function.__code__, function.__defaults__,
            tuple(sorted((function.__kwdefaults__ or {}).items())),
        )
        for function in (parsedate_to_datetime, *expected_capture_entrypoints)
    )
    object_names = (
        "Counter", "datetime", "timezone", "parsedate_to_datetime",
        "hashlib", "json", "re", "unicodedata", "_SHA_RE", "_ID_RE",
        "_UTC_RFC3339_RE", "_PRESENTED_RFC3339_RE", "_VERSION_TOKEN_RE",
    )
    expected_objects = tuple((name, module_globals[name]) for name in object_names)
    expected_attributes = (
        (hashlib, "sha256", hashlib.sha256),
        (json, "dumps", json.dumps), (json, "loads", json.loads),
        (re, "escape", re.escape), (re, "finditer", re.finditer),
        (re, "fullmatch", re.fullmatch),
        (unicodedata, "normalize", unicodedata.normalize),
        (unicodedata, "category", unicodedata.category),
    )
    expected_manifest = canonical_file_bytes(COMPONENT_MANIFEST)
    expected_literals = (
        ROW_SCHEMA, BUNDLE_SCHEMA, RECEIPT_SCHEMA, COMPONENT_VERSION,
        RECORD_ORIGIN, OPERATIONAL_EFFECT, GATE_STATUS, METRIC_STATUS,
        PREDECESSOR_COMPONENT_MANIFEST_SHA256, COMPONENT_MANIFEST_SHA256,
        EXPECTED_SEED_COUNT, MAX_ARTIFACT_BYTES,
        MAX_PAGE_REVISION_VALUE_CHARS, MAX_PAGE_REVISION_EVIDENCE_BYTES,
        MAX_PAGE_REVISION_SIGNALS, PAGE_REVISION_STATUSES,
        PAGE_REVISION_KINDS, PAGE_REVISION_VALUE_TYPES, PAGE_REVISION_SYNTAXES,
        _FALSE_CAPABILITIES, _PAGE_INPUT_FIELDS, _SIGNAL_INPUT_FIELDS,
        _SIGNAL_OUTPUT_FIELDS, _TRANSPORT_FIELDS,
        _PAGE_PROJECTION_FIELDS, _ROW_FIELDS, _BUNDLE_FIELDS, _RECEIPT_FIELDS,
    )

    def guard() -> None:
        for name, expected, code, defaults, kwdefaults in expected_functions:
            current = module_globals.get(name)
            if (
                current is not expected
                or getattr(current, "__code__", None) is not code
                or getattr(current, "__defaults__", None) != defaults
                or tuple(sorted((getattr(current, "__kwdefaults__", None) or {}).items()))
                != kwdefaults
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    f"runtime function integrity mismatch: {name}"
                )
        for name, expected in expected_objects:
            if module_globals.get(name) is not expected:
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    f"runtime object integrity mismatch: {name}"
                )
        for owner, name, expected in expected_attributes:
            if getattr(owner, name, None) is not expected:
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    f"runtime attribute integrity mismatch: {name}"
                )
        for function, code, defaults, kwdefaults in expected_external_functions:
            if (
                getattr(function, "__code__", None) is not code
                or getattr(function, "__defaults__", None) != defaults
                or tuple(sorted((getattr(function, "__kwdefaults__", None) or {}).items()))
                != kwdefaults
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                    "runtime external function integrity mismatch"
                )
        if (
            module_globals.get("capture_v1") is not expected_capture_module
            or capture_v1.validate_intake_bytes is not expected_capture_entrypoints[0]
            or capture_v1.validate_receipt_bytes is not expected_capture_entrypoints[1]
            or canonical_file_bytes(COMPONENT_MANIFEST) != expected_manifest
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "runtime predecessor/manifest integrity mismatch"
            )
        current_literals = (
            ROW_SCHEMA, BUNDLE_SCHEMA, RECEIPT_SCHEMA, COMPONENT_VERSION,
            RECORD_ORIGIN, OPERATIONAL_EFFECT, GATE_STATUS, METRIC_STATUS,
            PREDECESSOR_COMPONENT_MANIFEST_SHA256, COMPONENT_MANIFEST_SHA256,
            EXPECTED_SEED_COUNT, MAX_ARTIFACT_BYTES,
            MAX_PAGE_REVISION_VALUE_CHARS, MAX_PAGE_REVISION_EVIDENCE_BYTES,
            MAX_PAGE_REVISION_SIGNALS, PAGE_REVISION_STATUSES,
            PAGE_REVISION_KINDS, PAGE_REVISION_VALUE_TYPES,
            PAGE_REVISION_SYNTAXES, _FALSE_CAPABILITIES, _PAGE_INPUT_FIELDS,
            _SIGNAL_INPUT_FIELDS, _SIGNAL_OUTPUT_FIELDS, _TRANSPORT_FIELDS,
            _PAGE_PROJECTION_FIELDS, _ROW_FIELDS, _BUNDLE_FIELDS, _RECEIPT_FIELDS,
        )
        if current_literals != expected_literals:
            raise P0PresentedHttpCaptureTemporalEvidenceV2Error(
                "runtime literal integrity mismatch"
            )

    return guard


_RUNTIME_INTEGRITY_GUARD = _make_runtime_integrity_guard()


def _guard_public(implementation):
    guard = _RUNTIME_INTEGRITY_GUARD

    def guarded(*args: Any, **kwargs: Any):
        guard()
        result = implementation(*args, **kwargs)
        guard()
        return result

    guarded.__name__ = implementation.__name__.removeprefix("_").removesuffix("_impl")
    guarded.__doc__ = implementation.__doc__
    return guarded


build_artifact_bytes = _guard_public(_build_artifact_bytes_impl)
validate_artifact_bytes = _guard_public(_validate_artifact_bytes_impl)
build_receipt_bytes = _guard_public(_build_receipt_bytes_impl)
validate_receipt_bytes = _guard_public(_validate_receipt_bytes_impl)


__all__ = [
    "BUNDLE_SCHEMA", "COMPONENT_MANIFEST", "COMPONENT_MANIFEST_SHA256",
    "COMPONENT_VERSION", "GATE_STATUS", "PAGE_REVISION_KINDS",
    "PAGE_REVISION_STATUSES", "PAGE_REVISION_VALUE_TYPES",
    "PAGE_REVISION_SYNTAXES",
    "P0PresentedHttpCaptureTemporalEvidenceV2Error", "RECEIPT_SCHEMA",
    "ROW_SCHEMA", "build_artifact_bytes", "build_receipt_bytes",
    "canonical_bytes", "canonical_file_bytes", "canonical_sha256",
    "raw_sha256", "validate_artifact_bytes", "validate_receipt_bytes",
    "with_self_hash",
]
