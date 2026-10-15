"""Independent replay for the presented HTTP capture-intake V1 component.

The producer module is intentionally not imported.  Seed rows, component pins,
transport normalization, payload hashing, zero-credit gates, and receipt
projection are reconstructed from caller-original metadata and response bytes.
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
CHILD_RECEIPT_SCHEMA = "p0_presented_http_capture_intake_receipt_v1"
PARENT_RECEIPT_SCHEMA = "p0_presented_http_capture_intake_parent_receipt_v1"
COMPONENT_VERSION = "presented-http-capture-intake-v1"
ORIGIN = "PRESENTED_UNVERIFIED"
EFFECT = "NONE_SHADOW_ONLY"
GATE = "NO_GO_PRESENTED_HTTP_CAPTURE_INTAKE_ONLY"
PARENT_GATE = "NO_GO_INDEPENDENT_PRESENTED_HTTP_CAPTURE_INTAKE_REPLAY_ONLY"
METRIC = "NOT_ESTIMABLE"
SEED_COMPONENT_SHA = "52dcabd17c6d512643648e535f07cea4ab36e0af4f506da2a436150f356f219d"
SEED_RAW_SHA = "1c5b73f1edfc9c783435c9413e44bbeda4314aff5fc9abd75132f05691ef69b9"
EXPECTED_COMPONENT_MANIFEST_SHA256 = "e115cd8c8da2b7f4b09c0ff252055656ac206da062afc0fb9edbc517a8a77339"
MAX_REDIRECTS = 10
MAX_PAYLOAD = 4 * 1024 * 1024
MAX_ARTIFACT = 2 * 1024 * 1024

SEEDS = (
    ("seed-arca-novelchannel-abbreviation", "A", "https://arca.live/w/novelchannel/%EC%86%8C%EC%84%A4%20%EC%B6%95%EC%95%BD%EC%96%B4", "WORK_ALIAS_COLLABORATIVE_LIST", "lineage-arca-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-genrenovel-7614173", "A", "https://gall.dcinside.com/mgallery/board/view?id=genrenovel&no=7614173", "WORK_ALIAS_DASH_LIST_BACKUP", "lineage-arca-abbreviation-list", "BACKUP_SAME_LINEAGE"),
    ("seed-fmkorea-9330585139", "A", "https://www.fmkorea.com/9330585139", "WORK_ALIAS_EQUALS_LIST", "lineage-fmkorea-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-tgijjdd-217475", "B", "https://gall.dcinside.com/mgallery/board/view/?id=tgijjdd&no=217475", "COMMUNITY_GLOSSARY_FREE_PARAGRAPH", "lineage-dc-webnovel-jargon-list", "PRIMARY_CANDIDATE"),
    ("seed-tanma-ganadala", "B", "https://tanma.kr/data/webnovel_terms_ganadala.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-mabasa", "B", "https://tanma.kr/data/webnovel_terms_mabasa.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-ajacha", "B", "https://tanma.kr/data/webnovel_terms_ajacha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-katapaha", "B", "https://tanma.kr/data/webnovel_terms_katapaha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
)

FALSE_FIELDS = (
    "capture_authority_verified", "rights_authority_verified",
    "retention_authority_verified", "source_attestation_verified",
    "adapter_runtime_verified", "parser_execution_allowed",
    "claim_derivation_allowed", "derived_index_allowed",
    "publication_evidence_allowed", "metric_denominator_eligible",
    "actual_authority_granted", "production_approval", "full_scan_approval",
    "p0_phase_exit", "action_applied",
)
REDIRECT_FIELDS = frozenset({"hop_sequence", "from_url", "status_code", "location", "to_url"})
TIMESTAMP_FIELDS = frozenset({"date_header", "last_modified_header", "source_timestamp", "source_timestamp_basis", "evidence_sha256"})
PROVENANCE_FIELDS = frozenset({"presented_capture_id", "presented_collected_at", "clock_source", "clock_attestation_ref_sha256", "capture_tool_id", "capture_tool_manifest_sha256", "request_config_sha256", "response_representation", "content_encoding"})
ATTESTATION_FIELDS = frozenset({"artifact_role", "artifact_id", "artifact_sha256", "attestation_status"})
LOCATOR_FIELDS = frozenset({"payload_role", "payload_id", "coordinate_system", "start", "end", "payload_sha256"})
PRESENTED_FIELDS = frozenset({"seed_sequence", "seed_id", "source_id", "requested_url", "final_url", "redirect_hops", "terminal_http_status", "response_content_type", "source_timestamp_evidence", "capture_timing_provenance", "rights_attestation_ref", "retention_attestation_ref", "byte_locator"})
BUNDLE_FIELDS = frozenset({"schema_version", "record_origin", "component_version", "component_manifest_sha256", "seed_component_manifest_sha256", "seed_registry_raw_sha256", "seed_specifications_sha256", "rows", "row_count", "track_counts", "lineage_family_count", "rows_sha256", "payload_inventory_sha256", "raw_payload_exposed", "credited_actual_source_snapshot_count", "credited_actual_source_claim_count", "credited_actual_context_review_count", "metric_denominator", "metric_status", *FALSE_FIELDS, "operational_effect", "gate_status", "blockers", "artifact_sha256"})
CHILD_RECEIPT_FIELDS = frozenset({"schema_version", "record_origin", "component_version", "component_manifest_sha256", "seed_component_manifest_sha256", "seed_registry_raw_sha256", "intake_raw_sha256", "intake_artifact_sha256", "row_count", "track_counts", "lineage_family_count", "rows_sha256", "payload_inventory_sha256", "raw_payload_exposed", "redirect_chain_structure_verified", "payload_length_and_hash_verified", "seed_binding_verified", "rights_and_retention_remain_unattested", "actual_credit_count", "metric_denominator", "metric_status", *FALSE_FIELDS, "operational_effect", "gate_status", "blockers", "receipt_sha256"})
PARENT_RECEIPT_FIELDS = frozenset({"schema_version", "record_origin", "child_component_manifest_sha256", "seed_component_manifest_sha256", "seed_registry_raw_sha256", "intake_raw_sha256", "child_receipt_raw_sha256", "row_count", "track_counts", "lineage_family_count", "rows_sha256", "payload_inventory_sha256", "original_input_replayed", "raw_payload_exposed", "actual_credit_count", "metric_denominator", "metric_status", *FALSE_FIELDS, "operational_effect", "gate_status", "blockers", "receipt_sha256"})

_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_HTTP_TOKEN_PATTERN = r"[!#$%&'*+.^_`|~0-9a-z-]+"
_CONTENT_TYPE_RE = re.compile(
    rf"^(?P<type>{_HTTP_TOKEN_PATTERN})/(?P<subtype>{_HTTP_TOKEN_PATTERN})"
    rf"(?P<parameters>(?:; {_HTTP_TOKEN_PATTERN}={_HTTP_TOKEN_PATTERN})*)$"
)
_CONTENT_ENCODINGS = frozenset({"identity", "gzip", "br", "deflate"})
_REDIRECT_CODES = {301, 302, 303, 307, 308}


class P0PresentedHttpCaptureIntakeParentError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedHttpCaptureIntakeParentError("canonical JSON invalid") from exc


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedHttpCaptureIntakeParentError("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: _digest(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise P0PresentedHttpCaptureIntakeParentError("duplicate JSON key")
        output[key] = value
    return output


def _constant(value: str) -> None:
    raise P0PresentedHttpCaptureIntakeParentError(f"nonfinite JSON: {value}")


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_ARTIFACT or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedHttpCaptureIntakeParentError(f"{label} framing invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0PresentedHttpCaptureIntakeParentError(f"{label} NFC invalid")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError, TypeError) as exc:
        if isinstance(exc, P0PresentedHttpCaptureIntakeParentError):
            raise
        raise P0PresentedHttpCaptureIntakeParentError(f"{label} parse invalid") from exc
    if type(value) is not dict or raw != _file(value):
        raise P0PresentedHttpCaptureIntakeParentError(f"{label} canonical mismatch")
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedHttpCaptureIntakeParentError(f"{label} fields mismatch")
    return dict(value)


def _text(value: Any, field: str, maximum: int = 2048) -> str:
    if type(value) is not str or not value or value != value.strip() or len(value) > maximum or unicodedata.normalize("NFC", value) != value or any(ord(c) < 0x20 or unicodedata.category(c) in {"Cf", "Cs"} for c in value):
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} text invalid")
    return value


def _id(value: Any, field: str) -> str:
    text = _text(value, field, 256)
    if _ID.fullmatch(text) is None:
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} ID invalid")
    return text


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} SHA invalid")
    return value


def _int(value: Any, field: str, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} integer invalid")
    return value


def _time(value: Any, field: str) -> str:
    text = _text(value, field, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} timezone missing")
    return text


def _content_type(value: Any) -> str:
    text = _text(value, "response content type", 256)
    if not text.isascii() or text != text.lower():
        raise P0PresentedHttpCaptureIntakeParentError("response content type must be lowercase ASCII")
    match = _CONTENT_TYPE_RE.fullmatch(text)
    if match is None:
        raise P0PresentedHttpCaptureIntakeParentError("response content type grammar invalid")
    parameters = match.group("parameters")
    names = [part.split("=", 1)[0] for part in parameters.split("; ") if part]
    if len(names) != len(set(names)):
        raise P0PresentedHttpCaptureIntakeParentError("response content type parameters duplicate")
    return text


def _url(value: Any, field: str) -> str:
    text = _text(value, field, 4096)
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} URL invalid") from exc
    if not text.isascii() or parsed.scheme != "https" or parsed.hostname is None or parsed.netloc != parsed.netloc.lower() or parsed.username is not None or parsed.password is not None or parsed.fragment or port == 443 or "\\" in text or any(part in {".", ".."} for part in parsed.path.split("/")):
        raise P0PresentedHttpCaptureIntakeParentError(f"{field} HTTPS canonicalization invalid")
    return text


def _seed_rows() -> list[dict[str, Any]]:
    rows = []
    for sequence, (seed_id, track, url, hint, lineage, relation) in enumerate(SEEDS, start=1):
        material = {
            "schema_version": "p0_presented_source_seed_candidate_row_v1", "seed_sequence": sequence,
            "seed_id": seed_id, "track": track,
            "record_type": "WORK_ALIAS_LIST" if track == "A" else "COMMUNITY_LEXICON_LIST",
            "canonical_url": url, "format_hint": hint,
            "source_profile_status": "PENDING_CAPTURE_ADAPTER", "source_lineage": lineage,
            "independence_group_id": lineage, "lineage_relation": relation,
            "status": ORIGIN, "attested_at": None, "attestation_status": "NOT_ATTESTED",
            "capture_status": "NOT_RUN", "parser_status": "NOT_RUN",
            "rights_status": "UNKNOWN_FAIL_CLOSED", "semantic_status": "REFERENCE_CANDIDATE_ONLY",
            "independence_eligible": False, "raw_capture_allowed": False,
            "parser_execution_allowed": False, "claim_derivation_allowed": False,
            "derived_index_allowed": False, "publication_evidence_allowed": False,
        }
        rows.append({**material, "row_sha256": _digest(material)})
    return rows


def _validate_seed_raw(raw: bytes) -> list[dict[str, Any]]:
    expected = b"".join(_file(row) for row in _seed_rows())
    if _raw(raw) != SEED_RAW_SHA or raw != expected:
        raise P0PresentedHttpCaptureIntakeParentError("seed registry identity mismatch")
    return _seed_rows()


def _redirects(value: Any, requested: str, final_url: str) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > MAX_REDIRECTS:
        raise P0PresentedHttpCaptureIntakeParentError("redirect list invalid")
    current = requested
    seen = {requested}
    output = []
    for sequence, item in enumerate(value, start=1):
        row = _strict(item, REDIRECT_FIELDS, "redirect")
        from_url = _url(row["from_url"], "redirect from")
        to_url = _url(row["to_url"], "redirect to")
        status = _int(row["status_code"], "redirect status", 100, 599)
        location = _text(row["location"], "redirect location", 4096)
        if _int(row["hop_sequence"], "redirect sequence", 1) != sequence or status not in _REDIRECT_CODES or from_url != current or to_url in seen or urljoin(from_url, location) != to_url:
            raise P0PresentedHttpCaptureIntakeParentError("redirect continuity invalid")
        output.append({"hop_sequence": sequence, "from_url": from_url, "status_code": status, "location": location, "to_url": to_url})
        current = to_url
        seen.add(to_url)
    if current != final_url or (not output and final_url != requested):
        raise P0PresentedHttpCaptureIntakeParentError("redirect final URL invalid")
    return output


def _timestamp_evidence(value: Any) -> dict[str, Any]:
    row = _strict(value, TIMESTAMP_FIELDS, "timestamp evidence")
    date_header = None if row["date_header"] is None else _text(row["date_header"], "date_header", 128)
    modified = None if row["last_modified_header"] is None else _text(row["last_modified_header"], "last_modified_header", 128)
    source_time = None if row["source_timestamp"] is None else _time(row["source_timestamp"], "source_timestamp")
    basis = row["source_timestamp_basis"]
    if basis not in {"NOT_EXPOSED", "PRESENTED_HTTP_DATE", "PRESENTED_LAST_MODIFIED"} or (basis == "NOT_EXPOSED") != (source_time is None):
        raise P0PresentedHttpCaptureIntakeParentError("timestamp basis/value invalid")
    selected_header = date_header if basis == "PRESENTED_HTTP_DATE" else modified if basis == "PRESENTED_LAST_MODIFIED" else None
    if basis != "NOT_EXPOSED":
        if selected_header is None:
            raise P0PresentedHttpCaptureIntakeParentError("timestamp basis lacks selected HTTP header")
        try:
            header_instant = parsedate_to_datetime(selected_header)
            source_instant = datetime.fromisoformat(source_time.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise P0PresentedHttpCaptureIntakeParentError("HTTP timestamp evidence invalid") from exc
        if header_instant.tzinfo is None or header_instant.astimezone(timezone.utc) != source_instant.astimezone(timezone.utc):
            raise P0PresentedHttpCaptureIntakeParentError("HTTP timestamp/source instant mismatch")
    material = {"date_header": date_header, "last_modified_header": modified, "source_timestamp": source_time, "source_timestamp_basis": basis}
    digest = _digest(material)
    if _sha(row["evidence_sha256"], "timestamp evidence") != digest:
        raise P0PresentedHttpCaptureIntakeParentError("timestamp evidence hash invalid")
    return {**material, "evidence_sha256": digest}


def _provenance(value: Any, seed_id: str) -> dict[str, Any]:
    row = _strict(value, PROVENANCE_FIELDS, "capture provenance")
    if _id(row["presented_capture_id"], "capture id") != f"presented-http-capture:{seed_id}" or row["clock_source"] != "CALLER_PRESENTED_UNVERIFIED" or row["response_representation"] != "HTTP_CONTENT_DECODED_ENTITY_BYTES_V1":
        raise P0PresentedHttpCaptureIntakeParentError("capture provenance authority/identity invalid")
    output = dict(row)
    output["presented_collected_at"] = _time(row["presented_collected_at"], "presented_collected_at")
    output["capture_tool_id"] = _id(row["capture_tool_id"], "capture tool")
    encoding = _text(row["content_encoding"], "content encoding", 128)
    if not encoding.isascii() or encoding not in _CONTENT_ENCODINGS:
        raise P0PresentedHttpCaptureIntakeParentError("content encoding unsupported or noncanonical")
    output["content_encoding"] = encoding
    for field in ("clock_attestation_ref_sha256", "capture_tool_manifest_sha256", "request_config_sha256"):
        output[field] = _sha(row[field], field)
    return output


def _attestation(value: Any, seed_id: str, kind: str) -> dict[str, Any]:
    row = _strict(value, ATTESTATION_FIELDS, f"{kind} attestation")
    role = f"{kind.upper()}_ATTESTATION_CANDIDATE"
    artifact_id = f"presented-{kind}-attestation:{seed_id}"
    if row["artifact_role"] != role or row["artifact_id"] != artifact_id or row["attestation_status"] != "NOT_ATTESTED":
        raise P0PresentedHttpCaptureIntakeParentError(f"{kind} attestation authority invalid")
    return {"artifact_role": role, "artifact_id": artifact_id, "artifact_sha256": _sha(row["artifact_sha256"], f"{kind} SHA"), "attestation_status": "NOT_ATTESTED"}


def _locator(value: Any, seed_id: str, payload: bytes) -> dict[str, Any]:
    row = _strict(value, LOCATOR_FIELDS, "byte locator")
    digest = _raw(payload)
    if row["payload_role"] != "RAW_HTTP_RESPONSE_BODY" or row["payload_id"] != f"presented-http-body:{seed_id}" or row["coordinate_system"] != "ZERO_BASED_BYTE_OFFSETS_IN_RESPONSE_BODY" or _int(row["start"], "locator start") != 0 or _int(row["end"], "locator end") != len(payload) or _sha(row["payload_sha256"], "locator SHA") != digest:
        raise P0PresentedHttpCaptureIntakeParentError("byte locator binding invalid")
    return dict(row)


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    return parsed.scheme, str(parsed.hostname), parsed.port


def _normalize_record(value: Any, seed: Mapping[str, Any], payload: bytes) -> dict[str, Any]:
    row = _strict(value, PRESENTED_FIELDS, "presented record")
    sequence = _int(row["seed_sequence"], "seed_sequence", 1)
    seed_id = _id(row["seed_id"], "seed_id")
    source_id = _id(row["source_id"], "source_id")
    requested = _url(row["requested_url"], "requested_url")
    final_url = _url(row["final_url"], "final_url")
    if sequence != seed["seed_sequence"] or seed_id != seed["seed_id"] or source_id != seed_id or requested != seed["canonical_url"]:
        raise P0PresentedHttpCaptureIntakeParentError("seed binding invalid")
    if type(payload) is not bytes or len(payload) > MAX_PAYLOAD:
        raise P0PresentedHttpCaptureIntakeParentError("payload invalid")
    redirects = _redirects(row["redirect_hops"], requested, final_url)
    status = _int(row["terminal_http_status"], "terminal status", 200, 599)
    if status in {204, 205, 304} and len(payload) != 0:
        raise P0PresentedHttpCaptureIntakeParentError("terminal status/entity-body invalid")
    content_type = _content_type(row["response_content_type"])
    timestamp = _timestamp_evidence(row["source_timestamp_evidence"])
    provenance = _provenance(row["capture_timing_provenance"], seed_id)
    rights = _attestation(row["rights_attestation_ref"], seed_id, "rights")
    retention = _attestation(row["retention_attestation_ref"], seed_id, "retention")
    locator = _locator(row["byte_locator"], seed_id, payload)
    digest = _raw(payload)
    material = {
        "schema_version": ROW_SCHEMA, "record_origin": ORIGIN,
        "seed_sequence": sequence, "seed_id": seed_id, "source_id": source_id,
        "track": seed["track"], "format_hint": seed["format_hint"],
        "source_lineage": seed["source_lineage"], "lineage_relation": seed["lineage_relation"],
        "requested_url": requested, "final_url": final_url, "redirect_hops": redirects,
        "redirect_hop_count": len(redirects),
        "cross_origin_redirect_observed": _origin(requested) != _origin(final_url),
        "terminal_http_status": status, "response_content_type": content_type,
        "response_content_type_sha256": _digest(content_type),
        "raw_response_bytes": len(payload), "raw_response_sha256": digest,
        "source_timestamp_evidence": timestamp, "capture_timing_provenance": provenance,
        "rights_attestation_ref": rights, "retention_attestation_ref": retention,
        "byte_locator": locator, "capture_runtime_status": "NOT_RUN",
        "parser_status": "NOT_RUN", "attestation_status": "NOT_ATTESTED",
        "rights_status": "UNKNOWN_FAIL_CLOSED", "retention_status": "UNKNOWN_FAIL_CLOSED",
        "semantic_status": "NOT_EVALUATED", **{field: False for field in FALSE_FIELDS},
        "operational_effect": EFFECT,
    }
    return {**material, "row_sha256": _digest(material)}


def _inputs(seed_raw: bytes, records: Sequence[Mapping[str, Any]], payloads: Mapping[str, bytes]) -> list[dict[str, Any]]:
    seeds = _validate_seed_raw(seed_raw)
    if type(records) not in {list, tuple} or len(records) != 8:
        raise P0PresentedHttpCaptureIntakeParentError("record count invalid")
    ids = [str(seed["seed_id"]) for seed in seeds]
    if type(payloads) is not dict or list(payloads) != ids:
        raise P0PresentedHttpCaptureIntakeParentError("payload inventory invalid")
    return [_normalize_record(records[index], seed, payloads[str(seed["seed_id"])]) for index, seed in enumerate(seeds)]


def _payload_inventory(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"seed_sequence": row["seed_sequence"], "seed_id": row["seed_id"], "raw_response_bytes": row["raw_response_bytes"], "raw_response_sha256": row["raw_response_sha256"], "byte_locator_sha256": _digest(row["byte_locator"])} for row in rows]


def _bundle(seed_raw: bytes, records: Sequence[Mapping[str, Any]], payloads: Mapping[str, bytes]) -> dict[str, Any]:
    rows = _inputs(seed_raw, records, payloads)
    blockers = ["ACTUAL_CAPTURE_AUTHORITY_NOT_VERIFIED", "ACTUAL_SOURCE_ATTESTATION_NOT_VERIFIED", "PARSER_RUNTIME_NOT_RUN", "RAW_RESPONSE_BYTES_PRESENTED_ONLY", "RETENTION_ATTESTATION_NOT_VERIFIED", "RIGHTS_ATTESTATION_NOT_VERIFIED", "SEMANTIC_CREDIT_ZERO"]
    material = {
        "schema_version": BUNDLE_SCHEMA, "record_origin": ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "seed_component_manifest_sha256": SEED_COMPONENT_SHA,
        "seed_registry_raw_sha256": _raw(seed_raw),
        "seed_specifications_sha256": _digest([list(row) for row in SEEDS]),
        "rows": rows, "row_count": 8,
        "track_counts": dict(sorted(Counter(row["track"] for row in rows).items())),
        "lineage_family_count": len({row["source_lineage"] for row in rows}),
        "rows_sha256": _digest(rows), "payload_inventory_sha256": _digest(_payload_inventory(rows)),
        "raw_payload_exposed": False, "credited_actual_source_snapshot_count": 0,
        "credited_actual_source_claim_count": 0, "credited_actual_context_review_count": 0,
        "metric_denominator": 0, "metric_status": METRIC,
        **{field: False for field in FALSE_FIELDS}, "operational_effect": EFFECT,
        "gate_status": GATE, "blockers": blockers,
    }
    return _seal(material, "artifact_sha256")


def _child_receipt(intake_raw: bytes, seed_raw: bytes, records: Sequence[Mapping[str, Any]], payloads: Mapping[str, bytes]) -> dict[str, Any]:
    intake = _bundle(seed_raw, records, payloads)
    material = {
        "schema_version": CHILD_RECEIPT_SCHEMA, "record_origin": ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "seed_component_manifest_sha256": SEED_COMPONENT_SHA,
        "seed_registry_raw_sha256": _raw(seed_raw), "intake_raw_sha256": _raw(intake_raw),
        "intake_artifact_sha256": intake["artifact_sha256"], "row_count": 8,
        "track_counts": intake["track_counts"], "lineage_family_count": intake["lineage_family_count"],
        "rows_sha256": intake["rows_sha256"], "payload_inventory_sha256": intake["payload_inventory_sha256"],
        "raw_payload_exposed": False, "redirect_chain_structure_verified": True,
        "payload_length_and_hash_verified": True, "seed_binding_verified": True,
        "rights_and_retention_remain_unattested": True, "actual_credit_count": 0,
        "metric_denominator": 0, "metric_status": METRIC,
        **{field: False for field in FALSE_FIELDS}, "operational_effect": EFFECT,
        "gate_status": GATE, "blockers": intake["blockers"],
    }
    return _seal(material, "receipt_sha256")


def _validate_parent_replay_impl(
    *,
    seed_registry_raw: bytes,
    presented_records: Sequence[Mapping[str, Any]],
    raw_payloads_by_seed: Mapping[str, bytes],
    intake_raw: bytes,
    child_receipt_raw: bytes,
) -> dict[str, Any]:
    child_bundle = _strict(_object(intake_raw, "intake"), BUNDLE_FIELDS, "intake")
    expected_bundle = _bundle(seed_registry_raw, presented_records, raw_payloads_by_seed)
    if child_bundle != expected_bundle or intake_raw != _file(expected_bundle):
        raise P0PresentedHttpCaptureIntakeParentError("independent intake replay mismatch")
    child_receipt = _strict(_object(child_receipt_raw, "child receipt"), CHILD_RECEIPT_FIELDS, "child receipt")
    expected_receipt = _child_receipt(intake_raw, seed_registry_raw, presented_records, raw_payloads_by_seed)
    if child_receipt != expected_receipt or child_receipt_raw != _file(expected_receipt):
        raise P0PresentedHttpCaptureIntakeParentError("independent child receipt replay mismatch")
    material = {
        "schema_version": PARENT_RECEIPT_SCHEMA, "record_origin": ORIGIN,
        "child_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "seed_component_manifest_sha256": SEED_COMPONENT_SHA,
        "seed_registry_raw_sha256": _raw(seed_registry_raw),
        "intake_raw_sha256": _raw(intake_raw),
        "child_receipt_raw_sha256": _raw(child_receipt_raw), "row_count": 8,
        "track_counts": child_bundle["track_counts"],
        "lineage_family_count": child_bundle["lineage_family_count"],
        "rows_sha256": child_bundle["rows_sha256"],
        "payload_inventory_sha256": child_bundle["payload_inventory_sha256"],
        "original_input_replayed": True, "raw_payload_exposed": False,
        "actual_credit_count": 0, "metric_denominator": 0, "metric_status": METRIC,
        **{field: False for field in FALSE_FIELDS}, "operational_effect": EFFECT,
        "gate_status": PARENT_GATE, "blockers": child_bundle["blockers"],
    }
    receipt = _seal(material, "receipt_sha256")
    if set(receipt) != PARENT_RECEIPT_FIELDS:
        raise P0PresentedHttpCaptureIntakeParentError("parent receipt field drift")
    return receipt


def _make_runtime_integrity_guard():
    module_globals = globals()
    error_type = P0PresentedHttpCaptureIntakeParentError
    function_names = (
        "_canonical", "_file", "_digest", "_raw", "_seal", "_pairs", "_constant",
        "_object", "_strict", "_text", "_id", "_sha", "_int", "_time",
        "_content_type", "_url", "_seed_rows", "_validate_seed_raw", "_redirects",
        "_timestamp_evidence", "_provenance", "_attestation", "_locator", "_origin",
        "_normalize_record", "_inputs", "_payload_inventory", "_bundle",
        "_child_receipt", "_validate_parent_replay_impl",
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
        "ROW_SCHEMA", "BUNDLE_SCHEMA", "CHILD_RECEIPT_SCHEMA", "PARENT_RECEIPT_SCHEMA",
        "COMPONENT_VERSION", "ORIGIN", "EFFECT", "GATE", "PARENT_GATE", "METRIC",
        "SEED_COMPONENT_SHA", "SEED_RAW_SHA", "EXPECTED_COMPONENT_MANIFEST_SHA256",
        "MAX_REDIRECTS", "MAX_PAYLOAD", "MAX_ARTIFACT", "SEEDS", "FALSE_FIELDS",
        "REDIRECT_FIELDS", "TIMESTAMP_FIELDS", "PROVENANCE_FIELDS", "ATTESTATION_FIELDS",
        "LOCATOR_FIELDS", "PRESENTED_FIELDS", "BUNDLE_FIELDS", "CHILD_RECEIPT_FIELDS",
        "PARENT_RECEIPT_FIELDS", "_CONTENT_ENCODINGS", "_REDIRECT_CODES",
        "_HTTP_TOKEN_PATTERN",
    )
    expected_literals = tuple(
        (
            name, type(module_globals[name]),
            frozenset(module_globals[name])
            if type(module_globals[name]) is set else module_globals[name],
        )
        for name in literal_names
    )
    json_dumps = json.dumps
    json_loads = json.loads
    json_decode_error = json.JSONDecodeError
    hashlib_sha256 = hashlib.sha256
    unicode_normalize = unicodedata.normalize
    unicode_category = unicodedata.category
    expected_regexes = tuple(
        (name, module_globals[name], module_globals[name].pattern, module_globals[name].flags)
        for name in ("_SHA", "_ID", "_CONTENT_TYPE_RE")
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
            comparable = frozenset(current) if type(current) is set else current
            if type(current) is not expected_type or comparable != expected:
                raise error_type(f"runtime semantic constant tamper: {name}")

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


validate_parent_replay = _guard_public(_validate_parent_replay_impl)


__all__ = [
    "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "P0PresentedHttpCaptureIntakeParentError", "PARENT_RECEIPT_SCHEMA",
    "validate_parent_replay",
]
