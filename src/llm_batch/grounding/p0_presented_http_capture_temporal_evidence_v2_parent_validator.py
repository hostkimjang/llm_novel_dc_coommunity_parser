"""Producer-free parent replay for presented HTTP temporal evidence V2."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from . import p0_presented_http_capture_intake_v1_parent_validator as capture_parent


ROW_SCHEMA = "p0_presented_http_capture_temporal_evidence_row_v2"
BUNDLE_SCHEMA = "p0_presented_http_capture_temporal_evidence_bundle_v2"
CHILD_RECEIPT_SCHEMA = "p0_presented_http_capture_temporal_evidence_receipt_v2"
PARENT_RECEIPT_SCHEMA = "p0_presented_http_capture_temporal_evidence_parent_receipt_v2"
COMPONENT_VERSION = "presented-http-capture-temporal-evidence-v2"
ORIGIN = "PRESENTED_UNVERIFIED"
EFFECT = "NONE_SHADOW_ONLY"
GATE = "NO_GO_PRESENTED_TEMPORAL_EVIDENCE_ONLY"
PARENT_GATE = "NO_GO_PARENT_REPLAY_PRESENTED_TEMPORAL_EVIDENCE_ONLY"
METRIC = "NOT_ESTIMABLE"
EXPECTED_COMPONENT_MANIFEST_SHA256 = (
    "8961fb8c5cc798d04eef08370563d7407344a70da4b43ea685406024f4f2cb8b"
)
PREDECESSOR_COMPONENT_MANIFEST_SHA256 = (
    "e115cd8c8da2b7f4b09c0ff252055656ac206da062afc0fb9edbc517a8a77339"
)
EXPECTED_SEED_COUNT = 8
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_VALUE_CHARS = 128
MAX_SIGNALS = 3
MAX_CONTEXT_BYTES = 512

STATUSES = ("NOT_EXPOSED", "PRESENTED_LOCATED")
KINDS = ("NONE", "PUBLISHED_AT", "MODIFIED_AT", "VERSION_ID")
SYNTAXES = (
    "JSON_LD_DATE_PUBLISHED", "JSON_LD_DATE_MODIFIED",
    "OPEN_GRAPH_ARTICLE_PUBLISHED_TIME",
    "OPEN_GRAPH_ARTICLE_MODIFIED_TIME", "SITE_NATIVE_VERSION_TOKEN",
)
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_PRESENTED_TIME_RE = re.compile(
    r"^(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:Z|[+-][0-2][0-9]:[0-5][0-9])$"
)
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

FALSE_FIELDS = (
    "transport_time_authority_verified", "page_revision_authority_verified",
    "page_revision_parser_verified", "capture_authority_verified",
    "rights_authority_verified", "retention_authority_verified",
    "source_attestation_verified", "actual_source_snapshot_credited",
    "claim_derivation_allowed", "derived_index_allowed",
    "publication_evidence_allowed", "metric_denominator_eligible",
    "actual_authority_granted", "p0_phase_exit", "production_approval",
    "full_scan_approval", "action_applied",
)
PAGE_INPUT_FIELDS = frozenset({
    "seed_sequence", "seed_id", "capture_row_sha256",
    "native_revision_status", "signals", "record_sha256",
})
SIGNAL_INPUT_FIELDS = frozenset({
    "kind", "syntax", "context_start", "context_end", "value_start",
    "value_end", "context_sha256", "value_sha256", "presented_value",
    "normalized_value",
})
SIGNAL_OUTPUT_FIELDS = frozenset({
    "kind", "syntax", "context_start", "context_end", "value_start",
    "value_end", "context_sha256", "value_sha256", "normalized_value",
    "signal_sha256",
})
TRANSPORT_FIELDS = frozenset({
    "presented_collected_at", "clock_source",
    "clock_attestation_ref_sha256", "http_date_header",
    "http_date_instant", "http_date_role", "http_last_modified_header",
    "http_last_modified_instant", "http_last_modified_role",
    "legacy_source_timestamp", "legacy_source_timestamp_basis",
    "legacy_source_timestamp_role", "transport_observation_sha256",
})
PAGE_PROJECTION_FIELDS = frozenset({
    "native_revision_status", "signal_count", "signals",
    "revision_observation_identity_sha256", "presented_record_sha256",
    "page_revision_projection_sha256",
})
ROW_FIELDS = frozenset({
    "schema_version", "record_origin", "seed_sequence", "seed_id",
    "source_id", "track", "source_lineage", "final_url",
    "predecessor_row_sha256", "raw_response_bytes", "raw_response_sha256",
    "transport_observation", "page_native_revision_evidence",
    "transport_and_page_revision_separated",
    "http_headers_accepted_as_page_revision", *FALSE_FIELDS,
    "operational_effect", "row_sha256",
})
BUNDLE_FIELDS = frozenset({
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
    "metric_status", *FALSE_FIELDS, "operational_effect", "gate_status",
    "blockers", "artifact_sha256",
})
CHILD_RECEIPT_FIELDS = frozenset({
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
    *FALSE_FIELDS, "operational_effect", "gate_status", "blockers",
    "receipt_sha256",
})
PARENT_RECEIPT_FIELDS = frozenset({
    "schema_version", "record_origin", "child_component_manifest_sha256",
    "predecessor_component_manifest_sha256", "seed_registry_raw_sha256",
    "predecessor_intake_raw_sha256", "predecessor_receipt_raw_sha256",
    "temporal_artifact_raw_sha256", "child_receipt_raw_sha256",
    "row_count", "rows_sha256", "page_revision_presented_count",
    "page_revision_not_exposed_count", "page_revision_signal_count",
    "revision_observation_identities_sha256", "replay_idempotency_key_sha256",
    "http_date_present_count",
    "http_last_modified_present_count",
    "predecessor_parent_replay_verified",
    "parent_separate_implementation_replay_verified",
    "transport_page_revision_separation_verified",
    "all_presented_page_revision_spans_verified",
    "http_header_page_revision_promotion_count", "raw_payload_exposed",
    "actual_credit_count", "metric_denominator", "metric_status",
    *FALSE_FIELDS, "operational_effect", "gate_status", "blockers",
    "parent_receipt_sha256",
})


class P0PresentedHttpCaptureTemporalEvidenceV2ParentError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "canonical JSON invalid"
        ) from exc


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "raw input must be exact bytes"
        )
    return hashlib.sha256(raw).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: _digest(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "duplicate JSON key"
            )
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
        f"nonfinite JSON: {value}"
    )


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes or not raw or len(raw) > MAX_ARTIFACT_BYTES
        or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{label} framing invalid"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                f"{label} NFC invalid"
            )
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        if isinstance(exc, P0PresentedHttpCaptureTemporalEvidenceV2ParentError):
            raise
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{label} parse invalid"
        ) from exc
    if type(value) is not dict or raw != _file(value):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{label} canonical mismatch"
        )
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{label} fields mismatch"
        )
    return dict(value)


def _text(value: Any, field: str, maximum: int = 256) -> str:
    if (
        type(value) is not str or not value or value != value.strip()
        or len(value) > maximum or unicodedata.normalize("NFC", value) != value
        or any(ord(char) < 0x20 or unicodedata.category(char) in {"Cf", "Cs"} for char in value)
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{field} text invalid"
        )
    return value


def _id(value: Any, field: str) -> str:
    text = _text(value, field)
    if _ID_RE.fullmatch(text) is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{field} identifier invalid"
        )
    return text


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{field} SHA invalid"
        )
    return value


def _int(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{field} integer invalid"
        )
    return value


def _http_instant(value: Any, field: str) -> str | None:
    if value is None:
        return None
    text = _text(value, field, 128)
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError) as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{field} HTTP date invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            f"{field} timezone missing"
        )
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_time(value: str) -> str:
    if value.endswith("-00:00") or _PRESENTED_TIME_RE.fullmatch(value) is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "presented timestamp syntax invalid"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "presented timestamp invalid"
        ) from exc
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _transport(row: Mapping[str, Any]) -> dict[str, Any]:
    timing = row["capture_timing_provenance"]
    timestamps = row["source_timestamp_evidence"]
    date_header = timestamps["date_header"]
    modified_header = timestamps["last_modified_header"]
    date_instant = _http_instant(date_header, "HTTP Date")
    modified_instant = _http_instant(modified_header, "HTTP Last-Modified")
    capture_instant = _normalize_time(timing["presented_collected_at"])
    if (
        date_instant is not None and modified_instant is not None
        and modified_instant > date_instant
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "HTTP Last-Modified cannot follow HTTP Date"
        )
    if any(
        instant is not None and instant > capture_instant
        for instant in (date_instant, modified_instant)
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
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
    return _seal(material, "transport_observation_sha256")


def _page(
    value: Any,
    *,
    sequence: int,
    seed_id: str,
    capture_row_sha256: str,
    capture_observed_at: str,
    payload: bytes,
) -> dict[str, Any]:
    row = _strict(value, PAGE_INPUT_FIELDS, "page revision record")
    if (
        _int(row["seed_sequence"], "seed_sequence", 1) != sequence
        or _id(row["seed_id"], "seed_id") != seed_id
        or _sha(row["capture_row_sha256"], "capture_row_sha256")
        != capture_row_sha256
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "page revision seed/capture binding mismatch"
        )
    if (
        type(row["signals"]) is not list
        or len(row["signals"]) > MAX_SIGNALS
        or any(type(item) is not dict for item in row["signals"])
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "page revision signals must be exact objects"
        )
    _sha(row["record_sha256"], "record_sha256")
    _text(row["native_revision_status"], "native_revision_status", 32)
    for index, raw_signal in enumerate(row["signals"], start=1):
        signal = _strict(
            raw_signal, SIGNAL_INPUT_FIELDS, f"signal {index} preflight"
        )
        _text(signal["kind"], "kind", 32)
        _text(signal["syntax"], "syntax", 64)
        _text(signal["presented_value"], "presented_value", MAX_VALUE_CHARS)
        _text(signal["normalized_value"], "normalized_value", MAX_VALUE_CHARS)
        _sha(signal["context_sha256"], "context_sha256")
        _sha(signal["value_sha256"], "value_sha256")
        context_start = _int(signal["context_start"], "context_start", 0)
        context_end = _int(signal["context_end"], "context_end", 1)
        value_start = _int(signal["value_start"], "value_start", 0)
        value_end = _int(signal["value_end"], "value_end", 1)
        if (
            context_start >= context_end or context_end > len(payload)
            or value_start >= value_end or value_end > len(payload)
            or not (context_start <= value_start < value_end <= context_end)
            or context_end - context_start > MAX_CONTEXT_BYTES
            or value_end - value_start > MAX_VALUE_CHARS * 4
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "page revision locator preflight invalid"
            )
    input_material = dict(row)
    supplied_hash = _sha(input_material.pop("record_sha256"), "record_sha256")
    input_material["signals"] = sorted(
        input_material["signals"], key=lambda item: str(item.get("kind", ""))
    )
    if supplied_hash != _digest(input_material):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "page revision record hash mismatch"
        )
    status = row["native_revision_status"]
    signals = row["signals"]
    if status not in STATUSES:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "page revision classification invalid"
        )
    if status == "NOT_EXPOSED":
        if signals:
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "NOT_EXPOSED must have no signals"
            )
        return _seal({
            "native_revision_status": status, "signal_count": 0,
            "signals": [], "revision_observation_identity_sha256": None,
            "presented_record_sha256": supplied_hash,
        }, "page_revision_projection_sha256")
    if not signals or len(signals) > MAX_SIGNALS:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "page revision signal count invalid"
        )
    kind_order = {kind: index for index, kind in enumerate(KINDS)}
    allowed = {
        "PUBLISHED_AT": {
            "JSON_LD_DATE_PUBLISHED", "OPEN_GRAPH_ARTICLE_PUBLISHED_TIME",
        },
        "MODIFIED_AT": {
            "JSON_LD_DATE_MODIFIED", "OPEN_GRAPH_ARTICLE_MODIFIED_TIME",
        },
        "VERSION_ID": {"SITE_NATIVE_VERSION_TOKEN"},
    }
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_value_spans: list[tuple[int, int]] = []
    for index, raw_signal in enumerate(signals, start=1):
        signal = _strict(raw_signal, SIGNAL_INPUT_FIELDS, f"signal {index}")
        kind = signal["kind"]
        syntax = signal["syntax"]
        if kind not in allowed or kind in seen or syntax not in allowed[kind]:
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "page revision signal kind/syntax invalid"
            )
        cs = _int(signal["context_start"], "context_start", 0)
        ce = _int(signal["context_end"], "context_end", 1)
        vs = _int(signal["value_start"], "value_start", 0)
        ve = _int(signal["value_end"], "value_end", 1)
        if (
            cs >= ce or ce > len(payload) or ce - cs > MAX_CONTEXT_BYTES
            or not (cs <= vs < ve <= ce) or ve - vs > MAX_VALUE_CHARS * 4
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "page revision locator invalid"
            )
        if any(
            not (ve <= prior_start or vs >= prior_end)
            for prior_start, prior_end in seen_value_spans
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "page revision value span role overlap"
            )
        context = payload[cs:ce]
        evidence = payload[vs:ve]
        if (
            _sha(signal["context_sha256"], "context_sha256") != _raw(context)
            or _sha(signal["value_sha256"], "value_sha256") != _raw(evidence)
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "page revision locator hash mismatch"
            )
        try:
            presented = evidence.decode("utf-8", errors="strict")
            context.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "page revision locator UTF-8 invalid"
            ) from exc
        if presented != _text(signal["presented_value"], "presented_value", MAX_VALUE_CHARS):
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
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
                if isinstance(
                    exc, P0PresentedHttpCaptureTemporalEvidenceV2ParentError
                ):
                    raise
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "JSON-LD page revision context invalid"
                ) from exc
            field_name = (
                "datePublished" if kind == "PUBLISHED_AT" else "dateModified"
            )
            if (
                type(context_object) is not dict
                or context_object.get(field_name) != presented
                or any(type(item) in {dict, list} for item in context_object.values())
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "JSON-LD page revision marker/value mismatch"
                )
            relative_value_span = (vs - cs, ve - cs)
            marker_pattern = (
                rb'"' + field_name.encode("ascii") + rb'"\s*:\s*"('
                + re.escape(evidence) + rb')"'
            )
            if not any(
                match.span(1) == relative_value_span
                for match in re.finditer(marker_pattern, context)
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "JSON-LD marker/value locator mismatch"
                )
        elif syntax.startswith("OPEN_GRAPH_"):
            property_name = (
                "article:published_time"
                if kind == "PUBLISHED_AT" else "article:modified_time"
            )
            escaped_property = re.escape(property_name)
            escaped_value = re.escape(presented)
            patterns = (
                rf'<meta property="{escaped_property}" content="{escaped_value}"\s*/?>',
                rf'<meta content="{escaped_value}" property="{escaped_property}"\s*/?>',
            )
            if not any(re.fullmatch(pattern, context_text) for pattern in patterns):
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "Open Graph page revision marker/value mismatch"
                )
            content_marker = b'content="' + evidence + b'"'
            marker_start = context.find(content_marker)
            if (
                marker_start < 0
                or marker_start + len(b'content="') != vs - cs
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "Open Graph marker/value locator mismatch"
                )
        else:
            version_pattern = (
                rb'(?:^|[\t\n\r\f ])data-version="('
                + re.escape(evidence) + rb')"(?=$|[\t\n\r\f />])'
            )
            relative_value_span = (vs - cs, ve - cs)
            marker_locator_verified = False
            for match in re.finditer(version_pattern, context):
                if match.span(1) != relative_value_span:
                    continue
                absolute_marker_start = (
                    cs + match.start(1) - len(b'data-version="')
                )
                absolute_marker_end = cs + match.end(1) + 1
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
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "site-native version marker/value locator mismatch"
                )
        normalized = _text(signal["normalized_value"], "normalized_value", MAX_VALUE_CHARS)
        if kind in {"PUBLISHED_AT", "MODIFIED_AT"}:
            if normalized != _normalize_time(presented):
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "page timestamp normalization mismatch"
                )
        elif (
            not presented.isascii() or _VERSION_RE.fullmatch(presented) is None
            or normalized != presented
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "page version token invalid"
            )
        projected = _seal({
            "kind": kind, "syntax": syntax, "context_start": cs,
            "context_end": ce, "value_start": vs, "value_end": ve,
            "context_sha256": _raw(context), "value_sha256": _raw(evidence),
            "normalized_value": normalized,
        }, "signal_sha256")
        if set(projected) != SIGNAL_OUTPUT_FIELDS:
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "signal projection fields mismatch"
            )
        output.append(projected)
        seen.add(kind)
        seen_value_spans.append((vs, ve))
    output.sort(key=lambda item: kind_order[item["kind"]])
    by_kind = {item["kind"]: item for item in output}
    if (
        "PUBLISHED_AT" in by_kind and "MODIFIED_AT" in by_kind
        and by_kind["PUBLISHED_AT"]["normalized_value"]
        > by_kind["MODIFIED_AT"]["normalized_value"]
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "page revision chronology invalid"
        )
    try:
        observed = datetime.fromisoformat(capture_observed_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "capture observed timestamp invalid"
        ) from exc
    if observed.tzinfo is None:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "capture observed timestamp timezone missing"
        )
    observed_utc = observed.astimezone(timezone.utc)
    for item in output:
        if item["kind"] in {"PUBLISHED_AT", "MODIFIED_AT"}:
            page_instant = datetime.fromisoformat(
                item["normalized_value"].replace("Z", "+00:00")
            )
            if page_instant > observed_utc:
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "page revision follows capture observation"
                )
    observation_identity = _digest({
        "domain": "p0-page-native-revision-identity-v2",
        "capture_row_sha256": capture_row_sha256, "signals": output,
    })
    return _seal({
        "native_revision_status": status, "signal_count": len(output),
        "signals": output,
        "revision_observation_identity_sha256": observation_identity,
        "presented_record_sha256": supplied_hash,
    }, "page_revision_projection_sha256")


def _rows(
    intake: Mapping[str, Any],
    payloads: Mapping[str, bytes],
    page_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    predecessor_rows = intake["rows"]
    if type(page_records) not in {list, tuple} or len(page_records) != EXPECTED_SEED_COUNT:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "page revision records require exact seed count"
        )
    ids = [row["seed_id"] for row in predecessor_rows]
    if type(payloads) is not dict or list(payloads) != ids:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "payload inventory invalid"
        )
    result: list[dict[str, Any]] = []
    for index, predecessor in enumerate(predecessor_rows):
        seed_id = predecessor["seed_id"]
        page = _page(
            page_records[index], sequence=index + 1, seed_id=seed_id,
            capture_row_sha256=predecessor["row_sha256"],
            capture_observed_at=predecessor["capture_timing_provenance"]["presented_collected_at"],
            payload=payloads[seed_id],
        )
        result.append(_seal({
            "schema_version": ROW_SCHEMA, "record_origin": ORIGIN,
            "seed_sequence": index + 1, "seed_id": seed_id,
            "source_id": predecessor["source_id"], "track": predecessor["track"],
            "source_lineage": predecessor["source_lineage"],
            "final_url": predecessor["final_url"],
            "predecessor_row_sha256": predecessor["row_sha256"],
            "raw_response_bytes": predecessor["raw_response_bytes"],
            "raw_response_sha256": predecessor["raw_response_sha256"],
            "transport_observation": _transport(predecessor),
            "page_native_revision_evidence": page,
            "transport_and_page_revision_separated": True,
            "http_headers_accepted_as_page_revision": False,
            **{field: False for field in FALSE_FIELDS},
            "operational_effect": EFFECT,
        }, "row_sha256"))
    return result


def _bundle(
    intake_raw: bytes,
    intake_receipt_raw: bytes,
    intake: Mapping[str, Any],
    payloads: Mapping[str, bytes],
    page_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = _rows(intake, payloads, page_records)
    presented = sum(
        row["page_native_revision_evidence"]["native_revision_status"]
        == "PRESENTED_LOCATED" for row in rows
    )
    signal_count = sum(
        row["page_native_revision_evidence"]["signal_count"] for row in rows
    )
    replay_idempotency_key = _digest({
        "domain": "p0-presented-http-capture-temporal-evidence-v2-replay-idempotency",
        "predecessor_intake_raw_sha256": _raw(intake_raw),
        "predecessor_receipt_raw_sha256": _raw(intake_receipt_raw),
        "presented_page_revision_record_sha256s": [
            row["page_native_revision_evidence"]["presented_record_sha256"]
            for row in rows
        ],
    })
    material = {
        "schema_version": BUNDLE_SCHEMA, "record_origin": ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "predecessor_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
        "predecessor_intake_raw_sha256": _raw(intake_raw),
        "predecessor_receipt_raw_sha256": _raw(intake_receipt_raw),
        "rows": rows, "row_count": len(rows),
        "track_counts": dict(sorted(Counter(row["track"] for row in rows).items())),
        "rows_sha256": _digest(rows), "page_revision_presented_count": presented,
        "page_revision_not_exposed_count": len(rows) - presented,
        "page_revision_signal_count": signal_count,
        "revision_observation_identities_sha256": _digest([
            row["page_native_revision_evidence"]["revision_observation_identity_sha256"]
            for row in rows
        ]),
        "replay_idempotency_key_sha256": replay_idempotency_key,
        "http_date_present_count": sum(
            row["transport_observation"]["http_date_header"] is not None for row in rows
        ),
        "http_last_modified_present_count": sum(
            row["transport_observation"]["http_last_modified_header"] is not None
            for row in rows
        ),
        "http_header_page_revision_promotion_count": 0,
        "raw_payload_exposed": False,
        "credited_actual_source_snapshot_count": 0,
        "metric_denominator": 0, "metric_status": METRIC,
        **{field: False for field in FALSE_FIELDS},
        "operational_effect": EFFECT, "gate_status": GATE,
        "blockers": [
            "ACTUAL_CAPTURE_AUTHORITY_NOT_VERIFIED",
            "PAGE_NATIVE_REVISION_PARSER_NOT_VERIFIED",
            "PAGE_REVISION_EVIDENCE_PRESENTED_ONLY",
            "RETENTION_ATTESTATION_NOT_VERIFIED",
            "RIGHTS_ATTESTATION_NOT_VERIFIED",
            "TRANSPORT_CLOCK_AUTHORITY_NOT_VERIFIED",
        ],
    }
    return _seal(material, "artifact_sha256")


def _child_receipt(
    artifact_raw: bytes,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    material = {
        "schema_version": CHILD_RECEIPT_SCHEMA, "record_origin": ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "predecessor_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
        "predecessor_intake_raw_sha256": artifact["predecessor_intake_raw_sha256"],
        "predecessor_receipt_raw_sha256": artifact["predecessor_receipt_raw_sha256"],
        "temporal_artifact_raw_sha256": _raw(artifact_raw),
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
        "metric_denominator": 0, "metric_status": METRIC,
        **{field: False for field in FALSE_FIELDS},
        "operational_effect": EFFECT, "gate_status": GATE,
        "blockers": artifact["blockers"],
    }
    return _seal(material, "receipt_sha256")


def _validate_parent_replay_impl(
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
    intake_raw: bytes,
    intake_receipt_raw: bytes,
    page_revision_records: Sequence[Mapping[str, Any]],
    temporal_artifact_raw: bytes,
    child_receipt_raw: bytes,
) -> dict[str, Any]:
    try:
        capture_parent.validate_parent_replay(
            seed_registry_raw=seed_registry_raw,
            presented_records=presented_records,
            raw_payloads_by_seed=raw_payloads_by_seed,
            intake_raw=intake_raw, child_receipt_raw=intake_receipt_raw,
        )
    except Exception as exc:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "predecessor parent replay failed"
        ) from exc
    intake = _object(intake_raw, "predecessor intake")
    if (
        intake.get("component_manifest_sha256")
        != PREDECESSOR_COMPONENT_MANIFEST_SHA256
        or intake.get("row_count") != EXPECTED_SEED_COUNT
        or type(intake.get("rows")) is not list
    ):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "predecessor intake identity invalid"
        )
    expected_artifact = _bundle(
        intake_raw, intake_receipt_raw, intake, raw_payloads_by_seed,
        page_revision_records,
    )
    artifact = _strict(
        _object(temporal_artifact_raw, "temporal artifact"),
        BUNDLE_FIELDS, "temporal artifact",
    )
    if artifact != expected_artifact or temporal_artifact_raw != _file(expected_artifact):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "independent temporal artifact replay mismatch"
        )
    expected_child = _child_receipt(temporal_artifact_raw, expected_artifact)
    child = _strict(
        _object(child_receipt_raw, "child receipt"),
        CHILD_RECEIPT_FIELDS, "child receipt",
    )
    if child != expected_child or child_receipt_raw != _file(expected_child):
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "independent child receipt replay mismatch"
        )
    material = {
        "schema_version": PARENT_RECEIPT_SCHEMA, "record_origin": ORIGIN,
        "child_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "predecessor_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
        "seed_registry_raw_sha256": _raw(seed_registry_raw),
        "predecessor_intake_raw_sha256": _raw(intake_raw),
        "predecessor_receipt_raw_sha256": _raw(intake_receipt_raw),
        "temporal_artifact_raw_sha256": _raw(temporal_artifact_raw),
        "child_receipt_raw_sha256": _raw(child_receipt_raw),
        "row_count": artifact["row_count"], "rows_sha256": artifact["rows_sha256"],
        "page_revision_presented_count": artifact["page_revision_presented_count"],
        "page_revision_not_exposed_count": artifact["page_revision_not_exposed_count"],
        "page_revision_signal_count": artifact["page_revision_signal_count"],
        "revision_observation_identities_sha256": artifact["revision_observation_identities_sha256"],
        "replay_idempotency_key_sha256": artifact["replay_idempotency_key_sha256"],
        "http_date_present_count": artifact["http_date_present_count"],
        "http_last_modified_present_count": artifact["http_last_modified_present_count"],
        "predecessor_parent_replay_verified": True,
        "parent_separate_implementation_replay_verified": True,
        "transport_page_revision_separation_verified": True,
        "all_presented_page_revision_spans_verified": True,
        "http_header_page_revision_promotion_count": 0,
        "raw_payload_exposed": False, "actual_credit_count": 0,
        "metric_denominator": 0, "metric_status": METRIC,
        **{field: False for field in FALSE_FIELDS},
        "operational_effect": EFFECT, "gate_status": PARENT_GATE,
        "blockers": artifact["blockers"],
    }
    receipt = _seal(material, "parent_receipt_sha256")
    if set(receipt) != PARENT_RECEIPT_FIELDS:
        raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
            "parent receipt fields mismatch"
        )
    return receipt


def _make_runtime_integrity_guard():
    module_globals = globals()
    names = (
        "_canonical", "_file", "_digest", "_raw", "_seal", "_pairs",
        "_constant", "_object", "_strict", "_text", "_id", "_sha",
        "_int", "_http_instant", "_normalize_time", "_transport", "_page",
        "_rows", "_bundle", "_child_receipt", "_validate_parent_replay_impl",
    )
    expected_functions = tuple(
        (
            name, module_globals[name], module_globals[name].__code__,
            module_globals[name].__defaults__,
            tuple(sorted((module_globals[name].__kwdefaults__ or {}).items())),
        )
        for name in names
    )
    expected_predecessor_module = capture_parent
    expected_predecessor_entrypoint = capture_parent.validate_parent_replay
    expected_external_functions = tuple(
        (
            function, function.__code__, function.__defaults__,
            tuple(sorted((function.__kwdefaults__ or {}).items())),
        )
        for function in (parsedate_to_datetime, expected_predecessor_entrypoint)
    )
    object_names = (
        "Counter", "datetime", "timezone", "parsedate_to_datetime",
        "hashlib", "json", "re", "unicodedata", "_SHA_RE", "_ID_RE",
        "_PRESENTED_TIME_RE", "_VERSION_RE",
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
    expected_literals = (
        ROW_SCHEMA, BUNDLE_SCHEMA, CHILD_RECEIPT_SCHEMA, PARENT_RECEIPT_SCHEMA,
        COMPONENT_VERSION, ORIGIN, EFFECT, GATE, PARENT_GATE, METRIC,
        EXPECTED_COMPONENT_MANIFEST_SHA256,
        PREDECESSOR_COMPONENT_MANIFEST_SHA256, EXPECTED_SEED_COUNT,
        MAX_ARTIFACT_BYTES, MAX_VALUE_CHARS, MAX_SIGNALS, MAX_CONTEXT_BYTES,
        STATUSES, KINDS, SYNTAXES, FALSE_FIELDS, PAGE_INPUT_FIELDS,
        SIGNAL_INPUT_FIELDS, SIGNAL_OUTPUT_FIELDS, TRANSPORT_FIELDS,
        PAGE_PROJECTION_FIELDS, ROW_FIELDS, BUNDLE_FIELDS,
        CHILD_RECEIPT_FIELDS, PARENT_RECEIPT_FIELDS,
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
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    f"runtime function integrity mismatch: {name}"
                )
        for name, expected in expected_objects:
            if module_globals.get(name) is not expected:
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    f"runtime object integrity mismatch: {name}"
                )
        for owner, name, expected in expected_attributes:
            if getattr(owner, name, None) is not expected:
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    f"runtime attribute integrity mismatch: {name}"
                )
        for function, code, defaults, kwdefaults in expected_external_functions:
            if (
                getattr(function, "__code__", None) is not code
                or getattr(function, "__defaults__", None) != defaults
                or tuple(sorted((getattr(function, "__kwdefaults__", None) or {}).items()))
                != kwdefaults
            ):
                raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                    "runtime external function integrity mismatch"
                )
        if (
            module_globals.get("capture_parent") is not expected_predecessor_module
            or capture_parent.validate_parent_replay is not expected_predecessor_entrypoint
        ):
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "runtime predecessor integrity mismatch"
            )
        current_literals = (
            ROW_SCHEMA, BUNDLE_SCHEMA, CHILD_RECEIPT_SCHEMA,
            PARENT_RECEIPT_SCHEMA, COMPONENT_VERSION, ORIGIN, EFFECT, GATE,
            PARENT_GATE, METRIC, EXPECTED_COMPONENT_MANIFEST_SHA256,
            PREDECESSOR_COMPONENT_MANIFEST_SHA256, EXPECTED_SEED_COUNT,
            MAX_ARTIFACT_BYTES, MAX_VALUE_CHARS, MAX_SIGNALS,
            MAX_CONTEXT_BYTES, STATUSES, KINDS, SYNTAXES, FALSE_FIELDS,
            PAGE_INPUT_FIELDS, SIGNAL_INPUT_FIELDS, SIGNAL_OUTPUT_FIELDS,
            TRANSPORT_FIELDS, PAGE_PROJECTION_FIELDS, ROW_FIELDS,
            BUNDLE_FIELDS, CHILD_RECEIPT_FIELDS, PARENT_RECEIPT_FIELDS,
        )
        if current_literals != expected_literals:
            raise P0PresentedHttpCaptureTemporalEvidenceV2ParentError(
                "runtime literal integrity mismatch"
            )

    return guard


_RUNTIME_INTEGRITY_GUARD = _make_runtime_integrity_guard()


def _guard_public(implementation):
    guard = _RUNTIME_INTEGRITY_GUARD

    def guarded(**kwargs: Any) -> dict[str, Any]:
        guard()
        result = implementation(**kwargs)
        guard()
        return result

    guarded.__name__ = implementation.__name__.removeprefix("_").removesuffix("_impl")
    return guarded


validate_parent_replay = _guard_public(_validate_parent_replay_impl)


__all__ = [
    "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "P0PresentedHttpCaptureTemporalEvidenceV2ParentError",
    "PARENT_RECEIPT_SCHEMA", "validate_parent_replay",
]
