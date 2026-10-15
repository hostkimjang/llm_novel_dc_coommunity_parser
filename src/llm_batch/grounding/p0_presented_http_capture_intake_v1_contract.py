"""Presented-only HTTP capture intake for the fixed eight-source seed registry.

This component does not fetch URLs or attest that a capture happened.  It binds
caller-presented transport metadata to exact in-memory response bytes and emits
only redacted canonical JSON: raw response content is never copied to an
artifact or receipt.  Every authority, parser, semantic, indexing, publication,
metric, and production capability remains fail-closed.
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
from urllib.parse import urljoin, urlsplit


ROW_SCHEMA = "p0_presented_http_capture_intake_row_v1"
BUNDLE_SCHEMA = "p0_presented_http_capture_intake_bundle_v1"
RECEIPT_SCHEMA = "p0_presented_http_capture_intake_receipt_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_http_capture_intake_component_manifest_v1"
COMPONENT_VERSION = "presented-http-capture-intake-v1"
RECORD_ORIGIN = "PRESENTED_UNVERIFIED"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_HTTP_CAPTURE_INTAKE_ONLY"
METRIC_STATUS = "NOT_ESTIMABLE"

EXPECTED_SEED_COUNT = 8
MAX_REDIRECT_HOPS = 10
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
SEED_COMPONENT_MANIFEST_SHA256 = (
    "52dcabd17c6d512643648e535f07cea4ab36e0af4f506da2a436150f356f219d"
)
SEED_REGISTRY_RAW_SHA256 = (
    "1c5b73f1edfc9c783435c9413e44bbeda4314aff5fc9abd75132f05691ef69b9"
)

SEED_SPECIFICATIONS = (
    ("seed-arca-novelchannel-abbreviation", "A", "https://arca.live/w/novelchannel/%EC%86%8C%EC%84%A4%20%EC%B6%95%EC%95%BD%EC%96%B4", "WORK_ALIAS_COLLABORATIVE_LIST", "lineage-arca-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-genrenovel-7614173", "A", "https://gall.dcinside.com/mgallery/board/view?id=genrenovel&no=7614173", "WORK_ALIAS_DASH_LIST_BACKUP", "lineage-arca-abbreviation-list", "BACKUP_SAME_LINEAGE"),
    ("seed-fmkorea-9330585139", "A", "https://www.fmkorea.com/9330585139", "WORK_ALIAS_EQUALS_LIST", "lineage-fmkorea-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-tgijjdd-217475", "B", "https://gall.dcinside.com/mgallery/board/view/?id=tgijjdd&no=217475", "COMMUNITY_GLOSSARY_FREE_PARAGRAPH", "lineage-dc-webnovel-jargon-list", "PRIMARY_CANDIDATE"),
    ("seed-tanma-ganadala", "B", "https://tanma.kr/data/webnovel_terms_ganadala.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-mabasa", "B", "https://tanma.kr/data/webnovel_terms_mabasa.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-ajacha", "B", "https://tanma.kr/data/webnovel_terms_ajacha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-katapaha", "B", "https://tanma.kr/data/webnovel_terms_katapaha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
)

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_HTTP_TOKEN_PATTERN = r"[!#$%&'*+.^_`|~0-9a-z-]+"
_CONTENT_TYPE_RE = re.compile(
    rf"^(?P<type>{_HTTP_TOKEN_PATTERN})/(?P<subtype>{_HTTP_TOKEN_PATTERN})"
    rf"(?P<parameters>(?:; {_HTTP_TOKEN_PATTERN}={_HTTP_TOKEN_PATTERN})*)$"
)
_CONTENT_ENCODINGS = frozenset({"identity", "gzip", "br", "deflate"})
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_FALSE_CAPABILITIES = (
    "capture_authority_verified", "rights_authority_verified",
    "retention_authority_verified", "source_attestation_verified",
    "adapter_runtime_verified", "parser_execution_allowed",
    "claim_derivation_allowed", "derived_index_allowed",
    "publication_evidence_allowed", "metric_denominator_eligible",
    "actual_authority_granted", "production_approval", "full_scan_approval",
    "p0_phase_exit", "action_applied",
)
_FORBIDDEN_FIELDS = frozenset({
    "target_id", "target_work_id", "target_sense_id", "surface_text",
    "definition", "truth_kind", "truth_label", "judgment",
    "annotation_status", "publication_action", "raw_response",
    "raw_response_body", "payload_base64", "content_text",
})
_SEED_ROW_FIELDS = frozenset({
    "schema_version", "seed_sequence", "seed_id", "track", "record_type",
    "canonical_url", "format_hint", "source_profile_status",
    "source_lineage", "independence_group_id", "lineage_relation", "status",
    "attested_at", "attestation_status", "capture_status", "parser_status",
    "rights_status", "semantic_status", "independence_eligible",
    "raw_capture_allowed", "parser_execution_allowed",
    "claim_derivation_allowed", "derived_index_allowed",
    "publication_evidence_allowed", "row_sha256",
})
_REDIRECT_FIELDS = frozenset({
    "hop_sequence", "from_url", "status_code", "location", "to_url",
})
_TIMESTAMP_FIELDS = frozenset({
    "date_header", "last_modified_header", "source_timestamp",
    "source_timestamp_basis", "evidence_sha256",
})
_PROVENANCE_FIELDS = frozenset({
    "presented_capture_id", "presented_collected_at", "clock_source",
    "clock_attestation_ref_sha256", "capture_tool_id",
    "capture_tool_manifest_sha256", "request_config_sha256",
    "response_representation", "content_encoding",
})
_ATTESTATION_REF_FIELDS = frozenset({
    "artifact_role", "artifact_id", "artifact_sha256", "attestation_status",
})
_LOCATOR_FIELDS = frozenset({
    "payload_role", "payload_id", "coordinate_system", "start", "end",
    "payload_sha256",
})
_PRESENTED_FIELDS = frozenset({
    "seed_sequence", "seed_id", "source_id", "requested_url", "final_url",
    "redirect_hops", "terminal_http_status", "response_content_type",
    "source_timestamp_evidence", "capture_timing_provenance",
    "rights_attestation_ref", "retention_attestation_ref", "byte_locator",
})
_ROW_FIELDS = frozenset({
    "schema_version", "record_origin", "seed_sequence", "seed_id",
    "source_id", "track", "format_hint", "source_lineage",
    "lineage_relation", "requested_url", "final_url", "redirect_hops",
    "redirect_hop_count", "cross_origin_redirect_observed",
    "terminal_http_status", "response_content_type",
    "response_content_type_sha256", "raw_response_bytes",
    "raw_response_sha256", "source_timestamp_evidence",
    "capture_timing_provenance", "rights_attestation_ref",
    "retention_attestation_ref", "byte_locator", "capture_runtime_status",
    "parser_status", "attestation_status", "rights_status",
    "retention_status", "semantic_status", *_FALSE_CAPABILITIES,
    "operational_effect", "row_sha256",
})
_BUNDLE_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version",
    "component_manifest_sha256", "seed_component_manifest_sha256",
    "seed_registry_raw_sha256", "seed_specifications_sha256", "rows",
    "row_count", "track_counts", "lineage_family_count",
    "rows_sha256", "payload_inventory_sha256", "raw_payload_exposed",
    "credited_actual_source_snapshot_count", "credited_actual_source_claim_count",
    "credited_actual_context_review_count", "metric_denominator",
    "metric_status", *_FALSE_CAPABILITIES, "operational_effect",
    "gate_status", "blockers", "artifact_sha256",
})
_RECEIPT_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version",
    "component_manifest_sha256", "seed_component_manifest_sha256",
    "seed_registry_raw_sha256", "intake_raw_sha256",
    "intake_artifact_sha256", "row_count", "track_counts",
    "lineage_family_count", "rows_sha256", "payload_inventory_sha256",
    "raw_payload_exposed", "redirect_chain_structure_verified",
    "payload_length_and_hash_verified", "seed_binding_verified",
    "rights_and_retention_remain_unattested", "actual_credit_count",
    "metric_denominator", "metric_status", *_FALSE_CAPABILITIES,
    "operational_effect", "gate_status", "blockers", "receipt_sha256",
})


class P0PresentedHttpCaptureIntakeError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedHttpCaptureIntakeError("canonical JSON invalid") from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedHttpCaptureIntakeError("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise P0PresentedHttpCaptureIntakeError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _constant(value: str) -> None:
    raise P0PresentedHttpCaptureIntakeError(f"non-finite JSON constant: {value}")


def _parse_object(raw: bytes, label: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes or not raw or len(raw) > MAX_ARTIFACT_BYTES
        or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw
    ):
        raise P0PresentedHttpCaptureIntakeError(f"{label} framing invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0PresentedHttpCaptureIntakeError(f"{label} must be NFC")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError, TypeError) as exc:
        if isinstance(exc, P0PresentedHttpCaptureIntakeError):
            raise
        raise P0PresentedHttpCaptureIntakeError(f"{label} parse invalid") from exc
    if type(value) is not dict or raw != canonical_file_bytes(value):
        raise P0PresentedHttpCaptureIntakeError(f"{label} canonical bytes mismatch")
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        missing = sorted(fields - set(value)) if isinstance(value, Mapping) else []
        extra = sorted(set(value) - fields) if isinstance(value, Mapping) else []
        raise P0PresentedHttpCaptureIntakeError(
            f"{label} fields mismatch: missing={missing}, extra={extra}"
        )
    if _FORBIDDEN_FIELDS.intersection(value):
        raise P0PresentedHttpCaptureIntakeError(f"{label} contains forbidden field")
    return dict(value)


def _text(value: Any, field: str, *, maximum: int = 2048) -> str:
    if (
        type(value) is not str or not value or value != value.strip()
        or len(value) > maximum or unicodedata.normalize("NFC", value) != value
        or any(ord(char) < 0x20 or unicodedata.category(char) in {"Cf", "Cs"} for char in value)
    ):
        raise P0PresentedHttpCaptureIntakeError(f"{field} text invalid")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field, maximum=256)
    if _ID_RE.fullmatch(text) is None:
        raise P0PresentedHttpCaptureIntakeError(f"{field} identifier invalid")
    return text


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedHttpCaptureIntakeError(f"{field} SHA-256 invalid")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise P0PresentedHttpCaptureIntakeError(f"{field} integer invalid")
    return value


def _timestamp(value: Any, field: str) -> str:
    text = _text(value, field, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedHttpCaptureIntakeError(f"{field} timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise P0PresentedHttpCaptureIntakeError(f"{field} timezone missing")
    return text


def _optional_text(value: Any, field: str, *, maximum: int = 2048) -> str | None:
    return None if value is None else _text(value, field, maximum=maximum)


def _content_type(value: Any) -> str:
    text = _text(value, "response_content_type", maximum=256)
    if not text.isascii() or text != text.lower():
        raise P0PresentedHttpCaptureIntakeError("response content type must be lowercase ASCII")
    match = _CONTENT_TYPE_RE.fullmatch(text)
    if match is None:
        raise P0PresentedHttpCaptureIntakeError("response content type grammar invalid")
    parameters = match.group("parameters")
    names = [part.split("=", 1)[0] for part in parameters.split("; ") if part]
    if len(names) != len(set(names)):
        raise P0PresentedHttpCaptureIntakeError("response content type parameters duplicate")
    return text


def _https_url(value: Any, field: str) -> str:
    text = _text(value, field, maximum=4096)
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise P0PresentedHttpCaptureIntakeError(f"{field} URL invalid") from exc
    hostname = parsed.hostname
    if (
        not text.isascii() or parsed.scheme != "https" or hostname is None
        or parsed.netloc != parsed.netloc.lower()
        or parsed.username is not None or parsed.password is not None
        or parsed.fragment or port == 443 or "\\" in text
        or any(part in {".", ".."} for part in parsed.path.split("/"))
    ):
        raise P0PresentedHttpCaptureIntakeError(f"{field} must be canonical HTTPS")
    return text


def _seed_rows_unchecked() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sequence, (seed_id, track, url, hint, lineage, relation) in enumerate(SEED_SPECIFICATIONS, start=1):
        material = {
            "schema_version": "p0_presented_source_seed_candidate_row_v1",
            "seed_sequence": sequence, "seed_id": seed_id, "track": track,
            "record_type": "WORK_ALIAS_LIST" if track == "A" else "COMMUNITY_LEXICON_LIST",
            "canonical_url": url, "format_hint": hint,
            "source_profile_status": "PENDING_CAPTURE_ADAPTER",
            "source_lineage": lineage, "independence_group_id": lineage,
            "lineage_relation": relation, "status": RECORD_ORIGIN,
            "attested_at": None, "attestation_status": "NOT_ATTESTED",
            "capture_status": "NOT_RUN", "parser_status": "NOT_RUN",
            "rights_status": "UNKNOWN_FAIL_CLOSED",
            "semantic_status": "REFERENCE_CANDIDATE_ONLY",
            "independence_eligible": False, "raw_capture_allowed": False,
            "parser_execution_allowed": False, "claim_derivation_allowed": False,
            "derived_index_allowed": False, "publication_evidence_allowed": False,
        }
        rows.append({**material, "row_sha256": canonical_sha256(material)})
    return rows


def build_expected_seed_registry_bytes() -> bytes:
    return b"".join(canonical_file_bytes(row) for row in _seed_rows_unchecked())


def _validate_seed_registry(raw: bytes) -> list[dict[str, Any]]:
    if type(raw) is not bytes or raw_sha256(raw) != SEED_REGISTRY_RAW_SHA256:
        raise P0PresentedHttpCaptureIntakeError("seed registry raw identity mismatch")
    expected = build_expected_seed_registry_bytes()
    if raw != expected:
        raise P0PresentedHttpCaptureIntakeError("seed registry exact rows mismatch")
    for row in _seed_rows_unchecked():
        _strict(row, _SEED_ROW_FIELDS, "seed row")
    return _seed_rows_unchecked()


def _normalize_redirects(value: Any, *, requested_url: str, final_url: str) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > MAX_REDIRECT_HOPS:
        raise P0PresentedHttpCaptureIntakeError("redirect_hops list invalid")
    current = requested_url
    seen = {requested_url}
    output: list[dict[str, Any]] = []
    for sequence, item in enumerate(value, start=1):
        hop = _strict(item, _REDIRECT_FIELDS, f"redirect hop {sequence}")
        if _integer(hop["hop_sequence"], "hop_sequence", minimum=1) != sequence:
            raise P0PresentedHttpCaptureIntakeError("redirect hop order mismatch")
        from_url = _https_url(hop["from_url"], "redirect from_url")
        to_url = _https_url(hop["to_url"], "redirect to_url")
        status = _integer(hop["status_code"], "redirect status", minimum=100, maximum=599)
        location = _text(hop["location"], "redirect location", maximum=4096)
        if status not in _REDIRECT_CODES or from_url != current or to_url in seen:
            raise P0PresentedHttpCaptureIntakeError("redirect chain inconsistent")
        if urljoin(from_url, location) != to_url:
            raise P0PresentedHttpCaptureIntakeError("redirect Location resolution mismatch")
        output.append({
            "hop_sequence": sequence, "from_url": from_url,
            "status_code": status, "location": location, "to_url": to_url,
        })
        current = to_url
        seen.add(to_url)
    if current != final_url or (not output and final_url != requested_url):
        raise P0PresentedHttpCaptureIntakeError("final URL/redirect chain mismatch")
    return output


def _timestamp_evidence(value: Any) -> dict[str, Any]:
    row = _strict(value, _TIMESTAMP_FIELDS, "source timestamp evidence")
    date_header = _optional_text(row["date_header"], "date_header", maximum=128)
    modified = _optional_text(row["last_modified_header"], "last_modified_header", maximum=128)
    source_timestamp = None if row["source_timestamp"] is None else _timestamp(row["source_timestamp"], "source_timestamp")
    basis = row["source_timestamp_basis"]
    allowed = {"NOT_EXPOSED", "PRESENTED_HTTP_DATE", "PRESENTED_LAST_MODIFIED"}
    if basis not in allowed:
        raise P0PresentedHttpCaptureIntakeError("source timestamp basis invalid")
    if basis == "NOT_EXPOSED" and source_timestamp is not None:
        raise P0PresentedHttpCaptureIntakeError("NOT_EXPOSED cannot carry source timestamp")
    if basis != "NOT_EXPOSED" and source_timestamp is None:
        raise P0PresentedHttpCaptureIntakeError("timestamp basis requires timestamp")
    selected_header = (
        date_header if basis == "PRESENTED_HTTP_DATE"
        else modified if basis == "PRESENTED_LAST_MODIFIED"
        else None
    )
    if basis != "NOT_EXPOSED":
        if selected_header is None:
            raise P0PresentedHttpCaptureIntakeError("timestamp basis lacks selected HTTP header")
        try:
            header_instant = parsedate_to_datetime(selected_header)
            source_instant = datetime.fromisoformat(source_timestamp.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise P0PresentedHttpCaptureIntakeError("HTTP timestamp evidence invalid") from exc
        if header_instant.tzinfo is None or header_instant.astimezone(timezone.utc) != source_instant.astimezone(timezone.utc):
            raise P0PresentedHttpCaptureIntakeError("HTTP timestamp/source instant mismatch")
    material = {
        "date_header": date_header, "last_modified_header": modified,
        "source_timestamp": source_timestamp, "source_timestamp_basis": basis,
    }
    if _sha(row["evidence_sha256"], "timestamp evidence SHA") != canonical_sha256(material):
        raise P0PresentedHttpCaptureIntakeError("source timestamp evidence hash mismatch")
    return {**material, "evidence_sha256": canonical_sha256(material)}


def _provenance(value: Any, seed_id: str) -> dict[str, Any]:
    row = _strict(value, _PROVENANCE_FIELDS, "capture timing provenance")
    expected_capture_id = f"presented-http-capture:{seed_id}"
    if _identifier(row["presented_capture_id"], "presented_capture_id") != expected_capture_id:
        raise P0PresentedHttpCaptureIntakeError("presented capture ID mismatch")
    if row["clock_source"] != "CALLER_PRESENTED_UNVERIFIED":
        raise P0PresentedHttpCaptureIntakeError("clock source cannot claim authority")
    if row["response_representation"] != "HTTP_CONTENT_DECODED_ENTITY_BYTES_V1":
        raise P0PresentedHttpCaptureIntakeError("response representation mismatch")
    output = dict(row)
    output["presented_collected_at"] = _timestamp(row["presented_collected_at"], "presented_collected_at")
    output["capture_tool_id"] = _identifier(row["capture_tool_id"], "capture_tool_id")
    encoding = _text(row["content_encoding"], "content_encoding", maximum=128)
    if not encoding.isascii() or encoding not in _CONTENT_ENCODINGS:
        raise P0PresentedHttpCaptureIntakeError("content_encoding unsupported or noncanonical")
    output["content_encoding"] = encoding
    for field in (
        "clock_attestation_ref_sha256", "capture_tool_manifest_sha256",
        "request_config_sha256",
    ):
        output[field] = _sha(row[field], field)
    return output


def _attestation_ref(value: Any, *, seed_id: str, kind: str) -> dict[str, Any]:
    row = _strict(value, _ATTESTATION_REF_FIELDS, f"{kind} attestation ref")
    role = f"{kind.upper()}_ATTESTATION_CANDIDATE"
    artifact_id = f"presented-{kind}-attestation:{seed_id}"
    if row["artifact_role"] != role or row["artifact_id"] != artifact_id:
        raise P0PresentedHttpCaptureIntakeError(f"{kind} attestation identity mismatch")
    if row["attestation_status"] != "NOT_ATTESTED":
        raise P0PresentedHttpCaptureIntakeError(f"{kind} attestation cannot claim authority")
    return {
        "artifact_role": role, "artifact_id": artifact_id,
        "artifact_sha256": _sha(row["artifact_sha256"], f"{kind} artifact SHA"),
        "attestation_status": "NOT_ATTESTED",
    }


def _locator(value: Any, *, seed_id: str, payload: bytes) -> dict[str, Any]:
    row = _strict(value, _LOCATOR_FIELDS, "byte locator")
    digest = raw_sha256(payload)
    if (
        row["payload_role"] != "RAW_HTTP_RESPONSE_BODY"
        or row["payload_id"] != f"presented-http-body:{seed_id}"
        or row["coordinate_system"] != "ZERO_BASED_BYTE_OFFSETS_IN_RESPONSE_BODY"
        or _integer(row["start"], "byte locator start") != 0
        or _integer(row["end"], "byte locator end") != len(payload)
        or _sha(row["payload_sha256"], "byte locator payload SHA") != digest
    ):
        raise P0PresentedHttpCaptureIntakeError("byte locator/payload mismatch")
    return dict(row)


def _origin_tuple(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    return parsed.scheme, str(parsed.hostname), parsed.port


def _normalize_presented_record(
    value: Any,
    *,
    seed: Mapping[str, Any],
    payload: bytes,
) -> dict[str, Any]:
    record = _strict(value, _PRESENTED_FIELDS, "presented capture record")
    sequence = _integer(record["seed_sequence"], "seed_sequence", minimum=1)
    seed_id = _identifier(record["seed_id"], "seed_id")
    source_id = _identifier(record["source_id"], "source_id")
    requested = _https_url(record["requested_url"], "requested_url")
    final_url = _https_url(record["final_url"], "final_url")
    if (
        sequence != seed["seed_sequence"] or seed_id != seed["seed_id"]
        or source_id != seed_id or requested != seed["canonical_url"]
    ):
        raise P0PresentedHttpCaptureIntakeError("capture/seed binding mismatch")
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE_BYTES:
        raise P0PresentedHttpCaptureIntakeError("raw response payload invalid")
    redirects = _normalize_redirects(
        record["redirect_hops"], requested_url=requested, final_url=final_url
    )
    status = _integer(record["terminal_http_status"], "terminal_http_status", minimum=200, maximum=599)
    if status in {204, 205, 304} and len(payload) != 0:
        raise P0PresentedHttpCaptureIntakeError("terminal status/entity-body mismatch")
    content_type = _content_type(record["response_content_type"])
    timestamp_evidence = _timestamp_evidence(record["source_timestamp_evidence"])
    provenance = _provenance(record["capture_timing_provenance"], seed_id)
    rights_ref = _attestation_ref(record["rights_attestation_ref"], seed_id=seed_id, kind="rights")
    retention_ref = _attestation_ref(record["retention_attestation_ref"], seed_id=seed_id, kind="retention")
    locator = _locator(record["byte_locator"], seed_id=seed_id, payload=payload)
    payload_digest = raw_sha256(payload)
    material = {
        "schema_version": ROW_SCHEMA, "record_origin": RECORD_ORIGIN,
        "seed_sequence": sequence, "seed_id": seed_id, "source_id": source_id,
        "track": seed["track"], "format_hint": seed["format_hint"],
        "source_lineage": seed["source_lineage"],
        "lineage_relation": seed["lineage_relation"],
        "requested_url": requested, "final_url": final_url,
        "redirect_hops": redirects, "redirect_hop_count": len(redirects),
        "cross_origin_redirect_observed": _origin_tuple(requested) != _origin_tuple(final_url),
        "terminal_http_status": status, "response_content_type": content_type,
        "response_content_type_sha256": canonical_sha256(content_type),
        "raw_response_bytes": len(payload), "raw_response_sha256": payload_digest,
        "source_timestamp_evidence": timestamp_evidence,
        "capture_timing_provenance": provenance,
        "rights_attestation_ref": rights_ref,
        "retention_attestation_ref": retention_ref, "byte_locator": locator,
        "capture_runtime_status": "NOT_RUN", "parser_status": "NOT_RUN",
        "attestation_status": "NOT_ATTESTED",
        "rights_status": "UNKNOWN_FAIL_CLOSED",
        "retention_status": "UNKNOWN_FAIL_CLOSED",
        "semantic_status": "NOT_EVALUATED",
        **{field: False for field in _FALSE_CAPABILITIES},
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "row_sha256": canonical_sha256(material)}


COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component_version": COMPONENT_VERSION, "record_origin": RECORD_ORIGIN,
    "seed_component_manifest_sha256": SEED_COMPONENT_MANIFEST_SHA256,
    "seed_registry_raw_sha256": SEED_REGISTRY_RAW_SHA256,
    "seed_specifications_sha256": canonical_sha256([list(row) for row in SEED_SPECIFICATIONS]),
    "expected_seed_count": EXPECTED_SEED_COUNT,
    "max_redirect_hops": MAX_REDIRECT_HOPS,
    "max_response_bytes": MAX_RESPONSE_BYTES,
    "terminal_status_minimum": 200,
    "entity_body_forbidden_statuses": [204, 205, 304],
    "source_timestamp_bases": [
        "NOT_EXPOSED", "PRESENTED_HTTP_DATE", "PRESENTED_LAST_MODIFIED",
    ],
    "response_representation": "HTTP_CONTENT_DECODED_ENTITY_BYTES_V1",
    "decoded_entity_representation_definition": (
        "raw_payloads_by_seed contains entity-body octets after every supported "
        "Content-Encoding has been removed; transfer framing is not included"
    ),
    "response_content_type_representation": "CANONICAL_PARSED_VALUE_NOT_RAW_HEADER_BYTES",
    "original_response_content_type_header_preserved": False,
    "response_content_type_grammar": "lowercase ASCII RFC token/type + token/subtype; optional unique '; token=token' parameters",
    "content_encoding_representation": "CALLER_PRESENTED_SINGLE_ORIGINAL_CODING_REMOVED_FROM_DECODED_ENTITY",
    "allowed_content_encodings": sorted(_CONTENT_ENCODINGS),
    "raw_payload_artifact_exposure_allowed": False,
    "network_access_allowed": False, "filesystem_access_allowed": False,
    "environment_access_allowed": False, "clock_access_allowed": False,
    "random_access_allowed": False, "subprocess_access_allowed": False,
    "import_side_effects_allowed": False, "actual_credit_allowed": False,
    "semantic_fields_allowed": False, "derived_index_allowed": False,
    "publication_evidence_allowed": False,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


def _normalize_inputs(
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
) -> list[dict[str, Any]]:
    seeds = _validate_seed_registry(seed_registry_raw)
    if type(presented_records) not in {list, tuple} or len(presented_records) != EXPECTED_SEED_COUNT:
        raise P0PresentedHttpCaptureIntakeError("presented records require exact seed count")
    expected_ids = [str(seed["seed_id"]) for seed in seeds]
    if type(raw_payloads_by_seed) is not dict or list(raw_payloads_by_seed) != expected_ids:
        raise P0PresentedHttpCaptureIntakeError("payload mapping requires exact ordered seed IDs")
    output = [
        _normalize_presented_record(
            presented_records[index], seed=seed,
            payload=raw_payloads_by_seed[str(seed["seed_id"])],
        )
        for index, seed in enumerate(seeds)
    ]
    if [row["seed_id"] for row in output] != expected_ids:
        raise P0PresentedHttpCaptureIntakeError("capture record order mismatch")
    return output


def _payload_inventory(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "seed_sequence": row["seed_sequence"], "seed_id": row["seed_id"],
            "raw_response_bytes": row["raw_response_bytes"],
            "raw_response_sha256": row["raw_response_sha256"],
            "byte_locator_sha256": canonical_sha256(row["byte_locator"]),
        }
        for row in rows
    ]


def _bundle_value(
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
) -> dict[str, Any]:
    rows = _normalize_inputs(seed_registry_raw, presented_records, raw_payloads_by_seed)
    blockers = [
        "ACTUAL_CAPTURE_AUTHORITY_NOT_VERIFIED",
        "ACTUAL_SOURCE_ATTESTATION_NOT_VERIFIED",
        "PARSER_RUNTIME_NOT_RUN",
        "RAW_RESPONSE_BYTES_PRESENTED_ONLY",
        "RETENTION_ATTESTATION_NOT_VERIFIED",
        "RIGHTS_ATTESTATION_NOT_VERIFIED",
        "SEMANTIC_CREDIT_ZERO",
    ]
    material = {
        "schema_version": BUNDLE_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "seed_component_manifest_sha256": SEED_COMPONENT_MANIFEST_SHA256,
        "seed_registry_raw_sha256": raw_sha256(seed_registry_raw),
        "seed_specifications_sha256": canonical_sha256([list(row) for row in SEED_SPECIFICATIONS]),
        "rows": rows, "row_count": len(rows),
        "track_counts": dict(sorted(Counter(row["track"] for row in rows).items())),
        "lineage_family_count": len({row["source_lineage"] for row in rows}),
        "rows_sha256": canonical_sha256(rows),
        "payload_inventory_sha256": canonical_sha256(_payload_inventory(rows)),
        "raw_payload_exposed": False,
        "credited_actual_source_snapshot_count": 0,
        "credited_actual_source_claim_count": 0,
        "credited_actual_context_review_count": 0,
        "metric_denominator": 0, "metric_status": METRIC_STATUS,
        **{field: False for field in _FALSE_CAPABILITIES},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
        "blockers": blockers,
    }
    return _seal(material, "artifact_sha256")


def _build_intake_bytes_impl(
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
) -> bytes:
    raw = canonical_file_bytes(
        _bundle_value(seed_registry_raw, presented_records, raw_payloads_by_seed)
    )
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise P0PresentedHttpCaptureIntakeError("intake artifact exceeds byte limit")
    return raw


def _validate_intake_bytes_impl(
    raw: bytes,
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
) -> dict[str, Any]:
    value = _strict(_parse_object(raw, "capture intake"), _BUNDLE_FIELDS, "capture intake")
    expected = _bundle_value(seed_registry_raw, presented_records, raw_payloads_by_seed)
    if value != expected:
        raise P0PresentedHttpCaptureIntakeError("capture intake replay mismatch")
    return value


def _receipt_value(
    intake_raw: bytes,
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
) -> dict[str, Any]:
    intake = _strict(
        _parse_object(intake_raw, "capture intake"), _BUNDLE_FIELDS, "capture intake"
    )
    expected_intake = _bundle_value(
        seed_registry_raw, presented_records, raw_payloads_by_seed
    )
    if intake != expected_intake:
        raise P0PresentedHttpCaptureIntakeError("capture intake replay mismatch")
    material = {
        "schema_version": RECEIPT_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "seed_component_manifest_sha256": SEED_COMPONENT_MANIFEST_SHA256,
        "seed_registry_raw_sha256": raw_sha256(seed_registry_raw),
        "intake_raw_sha256": raw_sha256(intake_raw),
        "intake_artifact_sha256": intake["artifact_sha256"],
        "row_count": intake["row_count"], "track_counts": intake["track_counts"],
        "lineage_family_count": intake["lineage_family_count"],
        "rows_sha256": intake["rows_sha256"],
        "payload_inventory_sha256": intake["payload_inventory_sha256"],
        "raw_payload_exposed": False, "redirect_chain_structure_verified": True,
        "payload_length_and_hash_verified": True, "seed_binding_verified": True,
        "rights_and_retention_remain_unattested": True,
        "actual_credit_count": 0, "metric_denominator": 0,
        "metric_status": METRIC_STATUS,
        **{field: False for field in _FALSE_CAPABILITIES},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
        "blockers": intake["blockers"],
    }
    return _seal(material, "receipt_sha256")


def _build_receipt_bytes_impl(
    intake_raw: bytes,
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
) -> bytes:
    return canonical_file_bytes(_receipt_value(
        intake_raw, seed_registry_raw=seed_registry_raw,
        presented_records=presented_records,
        raw_payloads_by_seed=raw_payloads_by_seed,
    ))


def _validate_receipt_bytes_impl(
    raw: bytes,
    *,
    intake_raw: bytes,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
) -> dict[str, Any]:
    value = _strict(_parse_object(raw, "capture intake receipt"), _RECEIPT_FIELDS, "capture intake receipt")
    expected = _receipt_value(
        intake_raw, seed_registry_raw=seed_registry_raw,
        presented_records=presented_records,
        raw_payloads_by_seed=raw_payloads_by_seed,
    )
    if value != expected:
        raise P0PresentedHttpCaptureIntakeError("capture intake receipt replay mismatch")
    return value


def _make_runtime_integrity_guard():
    module_globals = globals()
    error_type = P0PresentedHttpCaptureIntakeError
    function_names = (
        "canonical_bytes", "canonical_file_bytes", "canonical_sha256", "raw_sha256",
        "_seal", "_pairs", "_constant", "_parse_object", "_strict", "_text",
        "_identifier", "_sha", "_integer", "_timestamp", "_optional_text",
        "_content_type", "_https_url", "_seed_rows_unchecked",
        "build_expected_seed_registry_bytes", "_validate_seed_registry",
        "_normalize_redirects", "_timestamp_evidence", "_provenance",
        "_attestation_ref", "_locator", "_origin_tuple",
        "_normalize_presented_record", "_normalize_inputs", "_payload_inventory",
        "_bundle_value", "_build_intake_bytes_impl", "_validate_intake_bytes_impl",
        "_receipt_value", "_build_receipt_bytes_impl", "_validate_receipt_bytes_impl",
    )
    expected_functions = tuple(
        (
            name, module_globals[name], module_globals[name].__code__,
            module_globals[name].__defaults__,
            None if module_globals[name].__kwdefaults__ is None
            else tuple(sorted(module_globals[name].__kwdefaults__.items())),
        )
        for name in function_names
    )
    object_names = (
        "Counter", "datetime", "timezone", "parsedate_to_datetime", "hashlib",
        "json", "re", "unicodedata", "urljoin", "urlsplit",
    )
    expected_objects = tuple((name, module_globals[name]) for name in object_names)
    literal_names = (
        "ROW_SCHEMA", "BUNDLE_SCHEMA", "RECEIPT_SCHEMA", "COMPONENT_MANIFEST_SCHEMA",
        "COMPONENT_VERSION", "RECORD_ORIGIN", "OPERATIONAL_EFFECT", "GATE_STATUS",
        "METRIC_STATUS", "EXPECTED_SEED_COUNT", "MAX_REDIRECT_HOPS",
        "MAX_RESPONSE_BYTES", "MAX_ARTIFACT_BYTES", "SEED_COMPONENT_MANIFEST_SHA256",
        "SEED_REGISTRY_RAW_SHA256", "SEED_SPECIFICATIONS", "_CONTENT_ENCODINGS",
        "_HTTP_TOKEN_PATTERN", "_REDIRECT_CODES",
        "_FALSE_CAPABILITIES", "_FORBIDDEN_FIELDS", "_SEED_ROW_FIELDS",
        "_REDIRECT_FIELDS", "_TIMESTAMP_FIELDS", "_PROVENANCE_FIELDS",
        "_ATTESTATION_REF_FIELDS", "_LOCATOR_FIELDS", "_PRESENTED_FIELDS",
        "_ROW_FIELDS", "_BUNDLE_FIELDS", "_RECEIPT_FIELDS", "COMPONENT_MANIFEST_SHA256",
    )
    expected_literals = tuple(
        (name, type(module_globals[name]), module_globals[name]) for name in literal_names
    )
    manifest_object = COMPONENT_MANIFEST
    manifest_bytes = canonical_bytes(COMPONENT_MANIFEST)
    manifest_sha = COMPONENT_MANIFEST_SHA256
    json_dumps = json.dumps
    json_loads = json.loads
    json_decode_error = json.JSONDecodeError
    hashlib_sha256 = hashlib.sha256
    unicode_normalize = unicodedata.normalize
    unicode_category = unicodedata.category
    expected_regexes = tuple(
        (name, module_globals[name], module_globals[name].pattern, module_globals[name].flags)
        for name in ("_SHA_RE", "_ID_RE", "_CONTENT_TYPE_RE")
    )

    def guard() -> None:
        for name, expected in expected_objects:
            if module_globals.get(name) is not expected:
                raise error_type(f"runtime dependency alias tamper: {name}")
        if (
            json.dumps is not json_dumps or json.loads is not json_loads
            or json.JSONDecodeError is not json_decode_error
            or hashlib.sha256 is not hashlib_sha256
            or unicodedata.normalize is not unicode_normalize
            or unicodedata.category is not unicode_category
        ):
            raise error_type("runtime dependency callable tamper")
        for name, expected, pattern, flags in expected_regexes:
            current = module_globals.get(name)
            if current is not expected or current.pattern != pattern or current.flags != flags:
                raise error_type(f"runtime regex tamper: {name}")
        for name, expected, code, defaults, kwdefaults in expected_functions:
            current = module_globals.get(name)
            current_kwdefaults = (
                None if getattr(current, "__kwdefaults__", None) is None
                else tuple(sorted(current.__kwdefaults__.items()))
            )
            if (
                current is not expected or getattr(current, "__code__", None) is not code
                or getattr(current, "__defaults__", None) != defaults
                or current_kwdefaults != kwdefaults
            ):
                raise error_type(f"runtime helper/code/default tamper: {name}")
        for name, expected_type, expected in expected_literals:
            current = module_globals.get(name)
            if type(current) is not expected_type or current != expected:
                raise error_type(f"runtime semantic constant tamper: {name}")
        if (
            module_globals.get("COMPONENT_MANIFEST") is not manifest_object
            or canonical_bytes(COMPONENT_MANIFEST) != manifest_bytes
            or canonical_sha256(COMPONENT_MANIFEST) != manifest_sha
        ):
            raise error_type("runtime component manifest tamper")

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


build_intake_bytes = _guard_public(_build_intake_bytes_impl)
validate_intake_bytes = _guard_public(_validate_intake_bytes_impl)
build_receipt_bytes = _guard_public(_build_receipt_bytes_impl)
validate_receipt_bytes = _guard_public(_validate_receipt_bytes_impl)


__all__ = [
    "BUNDLE_SCHEMA", "COMPONENT_MANIFEST", "COMPONENT_MANIFEST_SHA256",
    "COMPONENT_VERSION", "GATE_STATUS", "MAX_REDIRECT_HOPS",
    "MAX_RESPONSE_BYTES", "P0PresentedHttpCaptureIntakeError",
    "RECEIPT_SCHEMA", "RECORD_ORIGIN", "ROW_SCHEMA",
    "SEED_COMPONENT_MANIFEST_SHA256", "SEED_REGISTRY_RAW_SHA256",
    "SEED_SPECIFICATIONS", "build_expected_seed_registry_bytes",
    "build_intake_bytes", "build_receipt_bytes", "canonical_file_bytes",
    "canonical_sha256", "validate_intake_bytes", "validate_receipt_bytes",
]
