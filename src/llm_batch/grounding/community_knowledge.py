"""Immutable, local community observations; neither source truth nor public authority.

Only load_snapshot reads files. Query uses original, separate text fragments and
explicit community/time. Local byte verification does not verify rights or
lineage assertions, and neutral parser observations do not determine meaning.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
import unicodedata

from .p0_source_profile_raw_parser_core import parse_capture, CORE_VERSION


MANIFEST_SCHEMA = "community_knowledge_snapshot_v1"
SOURCE_VIEW_SCHEMA = "community_knowledge_source_view_v1"
RECEIPT_SCHEMA = "community_knowledge_readback_v1"
QUERY_POLICY_VERSION = "community_exact_surface_v1"
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024
MAX_ROWS = 1000
MAX_SOURCES = 1000
MAX_PAYLOAD_BYTES = 256 * 1024
MAX_QUERY_CHARS = 12000
MAX_QUERY_FRAGMENTS = 128
MAX_COMPARISONS = 100000
MAX_OCCURRENCES = 32
MAX_SENSES = 16
MAX_RECEIPT_BYTES = 48 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BODY_PATH = re.compile(r"/(?:content|content_blocks/(?:0|[1-9][0-9]{0,8})/text)\Z")
_COMMENT_PATH = re.compile(r"/comments/(?:0|[1-9][0-9]{0,8})(?:/(?:content|text))?\Z")
_POLICY = {
    "query_policy_version": QUERY_POLICY_VERSION,
    "matching": "exact_raw_surface_unicode_word_boundaries",
    "time_policy": "available_and_valid_at_as_of_with_freeze_cutoff",
    "authority": "neutral_candidates_only",
    "max_query_chars": MAX_QUERY_CHARS, "max_query_fragments": MAX_QUERY_FRAGMENTS,
    "max_comparisons": MAX_COMPARISONS, "max_occurrences": MAX_OCCURRENCES,
    "max_senses": MAX_SENSES, "max_receipt_bytes": MAX_RECEIPT_BYTES,
    "max_snapshot_bytes": MAX_SNAPSHOT_BYTES, "max_rows": MAX_ROWS,
}
_CANDIDATE_ID_FIELDS = ("namespace", "surface_raw", "sense_candidate_id", "definition_text", "source_refs")
_SOURCE_FIELDS = {
    "source_id", "source_ref", "payload_ref", "payload_byte_sha256", "capture_profile",
    "capture_version", "normalization_version", "source_published_at", "source_modified_at",
    "captured_at", "available_at", "time_unknown_reason", "community_scope",
    "lineage_root_id", "parent_id", "derivation_kind", "lineage_status", "rights",
}
_REF_FIELDS = {"source_id", "utf8_byte_span_start", "utf8_byte_span_end", "evidence_text", "evidence_utf8_sha256"}


class CommunityKnowledgeError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def _fail(code: str, field: str = "") -> None:
    raise CommunityKnowledgeError(code, field)


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def row_content_sha256(row: dict) -> str:
    return canonical_sha256({key: value for key, value in row.items() if key != "row_content_sha256"})


def candidate_id_for(row: dict) -> str:
    return "candidate:" + canonical_sha256({key: row[key] for key in _CANDIDATE_ID_FIELDS})


def _obj(value: Any, required: set, field: str, optional=frozenset()) -> dict:
    if type(value) is not dict or not required <= value.keys() or value.keys() - required - optional:
        _fail("SCHEMA_INVALID", field)
    return value


def _text(value: Any, field: str, maximum=512, *, nullable=False) -> Any:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        _fail("FIELD_INVALID", field)
    try:
        value.encode("utf-8")
    except UnicodeError:
        _fail("FIELD_INVALID", field)
    if "\x00" in value:
        _fail("FIELD_INVALID", field)
    return value


def _enum(value: Any, allowed: set, field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail("ENUM_INVALID", field)
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        _fail("SHA256_INVALID", field)
    return value


def _date(value: Any, field: str, *, nullable=False) -> Any:
    if nullable and value is None:
        return None
    try:
        result = datetime.fromisoformat(_text(value, field, 64).replace("Z", "+00:00"))
    except ValueError:
        _fail("TIMESTAMP_INVALID", field)
    if result.tzinfo is None or result.utcoffset() is None:
        _fail("TIMESTAMP_INVALID", field)
    return result


def _strings(value: Any, field: str, maximum=32) -> list:
    if type(value) is not list or len(value) > maximum:
        _fail("LIST_INVALID", field)
    for item in value:
        _text(item, field, 128)
    if len(set(value)) != len(value):
        _fail("DUPLICATE_VALUE", field)
    return value


def _strict_json(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("DUPLICATE_JSON_KEY", key)
            result[key] = value
        return result
    def constant(_):
        _fail("NONFINITE_JSON")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CommunityKnowledgeError("JSON_INVALID") from exc


class _Files:
    def __init__(self, root: Path, manifest_size: int):
        self.root = root.resolve()
        self.total = manifest_size
        self.cache: dict[Path, bytes] = {}

    def read(self, relative: Any, expected: Any, maximum=MAX_SNAPSHOT_BYTES) -> bytes:
        name = _text(relative, "relative path", 512)
        _sha(expected, name)
        parts = PurePosixPath(name)
        if parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
            _fail("PATH_OUTSIDE_SNAPSHOT", name)
        try:
            path = self.root.joinpath(*parts.parts).resolve(strict=True)
            path.relative_to(self.root)
            if not path.is_file():
                _fail("FILE_INVALID", name)
            if path not in self.cache:
                with path.open("rb") as stream:
                    raw = stream.read(min(maximum, MAX_SNAPSHOT_BYTES - self.total) + 1)
                self.total += len(raw)
                if len(raw) > maximum or self.total > MAX_SNAPSHOT_BYTES:
                    _fail("SNAPSHOT_LIMIT_EXCEEDED", name)
                self.cache[path] = raw
            raw = self.cache[path]
        except (OSError, ValueError) as exc:
            if isinstance(exc, CommunityKnowledgeError):
                raise
            raise CommunityKnowledgeError("PATH_OR_FILE_INVALID", name) from exc
        if len(raw) > maximum:
            _fail("SNAPSHOT_LIMIT_EXCEEDED", name)
        if hashlib.sha256(raw).hexdigest() != expected:
            _fail("FILE_SHA256_MISMATCH", name)
        return raw


def _temporal(value: Any) -> None:
    scope = _obj(value, {"valid_from", "valid_to", "time_unknown_reason"}, "temporal_scope")
    start = _date(scope["valid_from"], "valid_from", nullable=True)
    end = _date(scope["valid_to"], "valid_to", nullable=True)
    _text(scope["time_unknown_reason"], "time_unknown_reason", nullable=True)
    if start is None and not scope["time_unknown_reason"]:
        _fail("TIME_UNKNOWN_REASON_MISSING", "valid_from")
    if start is not None and end is not None and start >= end:
        _fail("TIME_ORDER_INVALID", "temporal_scope")


def _review(value: Any, files: _Files, data_kind: str) -> None:
    item = _obj(value, {"authority", "reviewer", "receipt_ref", "receipt_sha256"}, "review")
    authority = _enum(item["authority"], {"HUMAN_REVIEW", "MODEL_REFERENCE", "SYNTHETIC_FIXTURE", "UNKNOWN"}, "review.authority")
    _text(item["reviewer"], "reviewer", nullable=True)
    if authority == "SYNTHETIC_FIXTURE" and data_kind != "SYNTHETIC_FIXTURE":
        _fail("SYNTHETIC_SOURCE_MIXED", "review")
    if authority != "UNKNOWN" and (not item["receipt_ref"] or not item["receipt_sha256"]):
        _fail("REVIEW_RECEIPT_MISSING")
    if item["receipt_ref"] is not None or item["receipt_sha256"] is not None:
        files.read(item["receipt_ref"], item["receipt_sha256"])


def _source(value: Any, files: _Files, data_kind: str, built_at: datetime) -> tuple[dict, set]:
    item = _obj(value, _SOURCE_FIELDS, "source")
    for field in ("source_id", "source_ref", "capture_profile", "capture_version", "normalization_version"):
        _text(item[field], field)
    _strings(item["community_scope"], "source.community_scope")
    _text(item["lineage_root_id"], "lineage_root_id", nullable=True)
    _text(item["parent_id"], "parent_id", nullable=True)
    lineage = _enum(item["lineage_status"], {"DECLARED", "UNKNOWN"}, "lineage_status")
    derivation = _enum(item["derivation_kind"], {"ORIGINAL", "MIRROR", "DERIVED", "UNKNOWN"}, "derivation_kind")
    if lineage == "DECLARED" and (not item["lineage_root_id"] or derivation == "UNKNOWN"):
        _fail("LINEAGE_INVALID")
    if derivation in {"MIRROR", "DERIVED"} and not item["parent_id"]:
        _fail("LINEAGE_INVALID", "parent_id")
    if item["parent_id"] == item["source_id"]:
        _fail("LINEAGE_INVALID", "self parent")
    times = {key: _date(item[key], key, nullable=True) for key in ("source_published_at", "source_modified_at", "captured_at", "available_at")}
    _text(item["time_unknown_reason"], "time_unknown_reason", nullable=True)
    if any(times[key] is None for key in ("source_published_at", "captured_at", "available_at")) and not item["time_unknown_reason"]:
        _fail("TIME_UNKNOWN_REASON_MISSING", "source")
    captured, available = times["captured_at"], times["available_at"]
    for key in ("source_published_at", "source_modified_at"):
        if times[key] is not None and captured is not None and times[key] > captured:
            _fail("TIME_ORDER_INVALID", key)
    if captured is not None and available is not None and captured > available:
        _fail("TIME_ORDER_INVALID", "available_at")
    if any(value is not None and value > built_at for value in times.values()):
        _fail("TIME_ORDER_INVALID", "built_at")
    rights = _obj(item["rights"], {"status", "basis_ref", "basis_sha256", "collection", "retention", "derived_index", "quotation", "reviewed_at", "takedown_status"}, "rights")
    status = _enum(rights["status"], {"REUSE_PERMITTED", "SYNTHETIC_FIXTURE", "UNKNOWN", "REVOKED"}, "rights.status")
    takedown = _enum(rights["takedown_status"], {"ACTIVE", "UNKNOWN", "REQUESTED", "REMOVED"}, "takedown_status")
    if status == "REVOKED" or takedown in {"REQUESTED", "REMOVED"}:
        _fail("RIGHTS_REVOKED_OR_TAKEDOWN", item["source_id"])
    if status == "SYNTHETIC_FIXTURE" and data_kind != "SYNTHETIC_FIXTURE":
        _fail("SYNTHETIC_SOURCE_MIXED", "rights")
    for key in ("collection", "retention", "derived_index", "quotation"):
        if rights[key] is not None and type(rights[key]) is not bool:
            _fail("FIELD_INVALID", "rights." + key)
    reviewed = _date(rights["reviewed_at"], "rights.reviewed_at", nullable=True)
    if reviewed is not None and reviewed > built_at:
        _fail("TIME_ORDER_INVALID", "rights.reviewed_at")
    if rights["basis_ref"] is not None or rights["basis_sha256"] is not None:
        files.read(rights["basis_ref"], rights["basis_sha256"])
    payload = files.read(item["payload_ref"], item["payload_byte_sha256"], MAX_PAYLOAD_BYTES)
    try:
        parsed = parse_capture(source_profile=item["capture_profile"], content_type="text/plain; charset=utf-8",
                               capture_version=item["capture_version"], normalization_version=item["normalization_version"], payload=payload)
    except ValueError as exc:
        raise CommunityKnowledgeError("CAPTURE_METADATA_INVALID") from exc
    observations = set()
    for observation in parsed.get("observations", []):
        observations.add((observation["utf8_byte_span_start"], observation["utf8_byte_span_end"],
                          observation["evidence_utf8_sha256"], observation["surface_text"], observation["presented_definition_text"]))
    return item, observations


def _row_hash(row: dict) -> None:
    if row_content_sha256(row) != _sha(row["row_content_sha256"], "row_content_sha256"):
        _fail("ROW_SHA256_MISMATCH")


def _candidate(value: Any, sources: dict, observations: dict, files: _Files, data_kind: str) -> dict:
    row = _obj(value, {"schema_version", "candidate_id", "namespace", "surface_raw", "surface_normalized", "sense_candidate_id", "definition_text", "relation_type", "review_status", "community_scope", "temporal_scope", "source_refs", "row_content_sha256"}, "candidate", {"review"})
    _enum(row["schema_version"], {"community_knowledge_candidate_v1"}, "candidate schema")
    _enum(row["namespace"], {"neutral_observation"}, "namespace")
    _enum(row["relation_type"], {"PRESENTED_EXPLICIT_DEFINITION_STATEMENT"}, "relation_type")
    _enum(row["review_status"], {"UNREVIEWED", "REVIEWED", "REJECTED"}, "review_status")
    for key, maximum in (("candidate_id", 128), ("sense_candidate_id", 128), ("surface_raw", 256), ("definition_text", 2048)):
        _text(row[key], key, maximum)
    if row["surface_normalized"] != unicodedata.normalize("NFC", row["surface_raw"]):
        _fail("NORMALIZATION_MISMATCH")
    _strings(row["community_scope"], "candidate.community_scope")
    _temporal(row["temporal_scope"])
    if row["review_status"] == "REVIEWED" and "review" not in row:
        _fail("REVIEW_RECEIPT_MISSING")
    if "review" in row:
        _review(row["review"], files, data_kind)
    if type(row["source_refs"]) is not list or not 1 <= len(row["source_refs"]) <= 8:
        _fail("SOURCE_REF_LIMIT_OR_MISSING")
    seen = set()
    for ref in row["source_refs"]:
        _obj(ref, _REF_FIELDS, "source_ref")
        sid = _text(ref["source_id"], "source_id")
        if sid not in sources:
            _fail("SOURCE_NOT_FOUND", sid)
        start, end = ref["utf8_byte_span_start"], ref["utf8_byte_span_end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= MAX_PAYLOAD_BYTES:
            _fail("SOURCE_SPAN_INVALID")
        evidence = _text(ref["evidence_text"], "evidence_text", 4096).encode("utf-8")
        evidence_sha = _sha(ref["evidence_utf8_sha256"], "evidence_utf8_sha256")
        source = sources[sid]
        raw = files.read(source["payload_ref"], source["payload_byte_sha256"], MAX_PAYLOAD_BYTES)
        if raw[start:end] != evidence or hashlib.sha256(evidence).hexdigest() != evidence_sha:
            _fail("SOURCE_SPAN_SHA256_MISMATCH")
        if (start, end, evidence_sha, row["surface_raw"], row["definition_text"]) not in observations[sid]:
            _fail("NEUTRAL_OBSERVATION_BINDING_MISMATCH")
        marker = canonical_sha256(ref)
        if marker in seen:
            _fail("DUPLICATE_SOURCE_REF")
        seen.add(marker)
    if row["candidate_id"] != candidate_id_for(row):
        _fail("CANDIDATE_ID_BINDING_MISMATCH")
    _row_hash(row)
    return row


def _classifications(rows: list, candidates: dict, files: _Files, data_kind: str, kind: str) -> dict:
    output: dict[str, list] = {}
    seen = set()
    for row in rows:
        if kind == "work_alias_registry":
            fields = {"schema_version", "registry_entry_id", "candidate_id", "review", "explicit_alias_assertion_ref", "work_id", "edition_id", "media_type", "canonical_title", "canonical_title_locator", "row_content_sha256"}
            _obj(row, fields, kind)
            _enum(row["schema_version"], {"community_knowledge_work_alias_v1"}, kind)
            identifier = _text(row["registry_entry_id"], "registry_entry_id", 128)
            for key in ("work_id", "media_type", "canonical_title", "canonical_title_locator"):
                _text(row[key], key)
            _text(row["edition_id"], "edition_id", nullable=True)
        else:
            fields = {"schema_version", "lexicon_entry_id", "candidate_id", "sense_id", "definition", "term_kind", "community_scope", "temporal_scope", "competing_sense_ids", "review", "row_content_sha256"}
            _obj(row, fields, kind, {"work_id"})
            _enum(row["schema_version"], {"community_knowledge_lexicon_v1"}, kind)
            identifier = _text(row["lexicon_entry_id"], "lexicon_entry_id", 128)
            _enum(row["term_kind"], {"GENERAL_SLANG", "MEME", "PLATFORM_TERM", "NARRATIVE_DEVICE", "UNKNOWN"}, "term_kind")
            _strings(row["competing_sense_ids"], "competing_sense_ids")
            if row.get("work_id") is not None:
                _fail("LEXICON_WORK_AUTHORITY_FORBIDDEN")
        if identifier in seen:
            _fail("DUPLICATE_ID", identifier)
        seen.add(identifier)
        cid = _text(row["candidate_id"], "candidate_id", 128)
        if cid not in candidates:
            _fail("CANDIDATE_NOT_FOUND", cid)
        candidate = candidates[cid]
        if kind == "work_alias_registry":
            if row["explicit_alias_assertion_ref"] not in candidate["source_refs"]:
                _fail("ALIAS_ASSERTION_BINDING_MISMATCH")
        else:
            for field, parent in (("sense_id", "sense_candidate_id"), ("definition", "definition_text"), ("community_scope", "community_scope"), ("temporal_scope", "temporal_scope")):
                if row[field] != candidate[parent]:
                    _fail("LEXICON_BINDING_MISMATCH", field)
        _review(row["review"], files, data_kind)
        _row_hash(row)
        output.setdefault(cid, []).append(row)
    return output


def load_snapshot(manifest_path: Any, expected_sha256: str) -> "FrozenCommunityKnowledge":
    """Verify explicit local bytes once. Raise a coded error; never infer sources."""
    expected = _sha(expected_sha256, "expected_sha256")
    try:
        path = Path(manifest_path).resolve(strict=True)
        with path.open("rb") as stream:
            raw = stream.read(MAX_SNAPSHOT_BYTES + 1)
    except (OSError, TypeError, ValueError) as exc:
        raise CommunityKnowledgeError("MANIFEST_READ_FAILED") from exc
    if len(raw) > MAX_SNAPSHOT_BYTES:
        _fail("SNAPSHOT_LIMIT_EXCEEDED")
    if hashlib.sha256(raw).hexdigest() != expected:
        _fail("SNAPSHOT_SHA256_MISMATCH")
    manifest = _obj(_strict_json(raw), {"schema_version", "snapshot_id", "data_kind", "built_at", "freeze_cutoff", "parser_version", "normalization_version", "query_policy_version", "rights_policy_version", "lineage_policy_version", "files"}, "manifest")
    versions = {"schema_version": MANIFEST_SCHEMA, "parser_version": CORE_VERSION,
                "normalization_version": "utf8_identity_v1", "query_policy_version": QUERY_POLICY_VERSION,
                "rights_policy_version": "local_asserted_reuse_v1", "lineage_policy_version": "declared_root_no_independent_authority_v1"}
    for key, wanted in versions.items():
        if manifest[key] != wanted:
            _fail("VERSION_UNSUPPORTED", key)
    _text(manifest["snapshot_id"], "snapshot_id", 128)
    data_kind = _enum(manifest["data_kind"], {"SYNTHETIC_FIXTURE", "SOURCE_BACKED"}, "data_kind")
    built_at = _date(manifest["built_at"], "built_at")
    if _date(manifest["freeze_cutoff"], "freeze_cutoff") > built_at:
        _fail("TIME_ORDER_INVALID", "freeze_cutoff")
    specs = _obj(manifest["files"], {"candidate_ledger", "work_alias_registry", "community_lexicon", "source_inventory"}, "files")
    files = _Files(path.parent, len(raw))
    loaded = {}
    total_rows = 0
    for name, spec in specs.items():
        count_key = "source_count" if name == "source_inventory" else "rows"
        _obj(spec, {"path", "sha256", count_key}, name)
        count = spec[count_key]
        if type(count) is not int or not 0 <= count <= MAX_ROWS:
            _fail("SNAPSHOT_LIMIT_EXCEEDED", name)
        content = files.read(spec["path"], spec["sha256"])
        if name == "source_inventory":
            inventory = _obj(_strict_json(content), {"schema_version", "sources"}, name)
            _enum(inventory["schema_version"], {"community_knowledge_source_inventory_v1"}, name)
            rows = inventory["sources"]
            if type(rows) is not list or len(rows) > MAX_SOURCES:
                _fail("SOURCE_LIMIT_EXCEEDED")
        else:
            lines = content.splitlines()
            if any(not line.strip() for line in lines):
                _fail("JSONL_BLANK_ROW", name)
            if len(lines) > MAX_ROWS:
                _fail("SNAPSHOT_LIMIT_EXCEEDED", name)
            rows = [_strict_json(line) for line in lines]
            total_rows += len(rows)
            if total_rows > MAX_ROWS:
                _fail("SNAPSHOT_LIMIT_EXCEEDED", "total rows")
        if len(rows) != count:
            _fail("ROW_COUNT_MISMATCH", name)
        loaded[name] = rows
    sources, observations = {}, {}
    for value in loaded["source_inventory"]:
        source, spans = _source(value, files, data_kind, built_at)
        sid = source["source_id"]
        if sid in sources:
            _fail("DUPLICATE_ID", sid)
        sources[sid], observations[sid] = source, spans
    # Known parent links may not contradict their declared root or form cycles.
    for sid, source in sources.items():
        seen = {sid}
        current = source
        while current["parent_id"] in sources:
            parent = sources[current["parent_id"]]
            if parent["source_id"] in seen:
                _fail("LINEAGE_CYCLE")
            seen.add(parent["source_id"])
            if current["lineage_status"] == parent["lineage_status"] == "DECLARED" and current["lineage_root_id"] != parent["lineage_root_id"]:
                _fail("LINEAGE_ROOT_CONFLICT")
            current = parent
    candidates, senses = {}, {}
    for value in loaded["candidate_ledger"]:
        row = _candidate(value, sources, observations, files, data_kind)
        cid, sense = row["candidate_id"], row["sense_candidate_id"]
        if cid in candidates:
            _fail("DUPLICATE_ID", cid)
        identity = canonical_sha256({key: row[key] for key in ("surface_raw", "definition_text", "community_scope", "temporal_scope")})
        if sense in senses and senses[sense] != identity:
            _fail("SENSE_ID_CONFLICT", sense)
        senses[sense] = identity
        candidates[cid] = row
    aliases = _classifications(loaded["work_alias_registry"], candidates, files, data_kind, "work_alias_registry")
    lexicon = _classifications(loaded["community_lexicon"], candidates, files, data_kind, "community_lexicon")
    bundle = {"manifest": manifest, "sources": sources, "candidates": sorted(candidates.values(), key=lambda row: row["candidate_id"]), "aliases": aliases, "lexicon": lexicon}
    counts = {key: len(rows) for key, rows in loaded.items()}
    summary = {"schema_version": "community_knowledge_snapshot_summary_v1", "mode": "READ_ONLY",
               "snapshot_sha256": expected, "config_sha256": canonical_sha256(_POLICY), "status": "AVAILABLE",
               "reason_codes": [], "data_kind": data_kind, "snapshot_id": manifest["snapshot_id"], "counts": counts,
               "public_authority": False, "central_db_write": False, "public_apply": False}
    return FrozenCommunityKnowledge(_bytes(summary), _bytes(bundle))


def unavailable_snapshot(reason: str, expected_sha256: Any = None) -> "FrozenCommunityKnowledge":
    if expected_sha256 is not None:
        _sha(expected_sha256, "expected_sha256")
    summary = {"schema_version": "community_knowledge_snapshot_summary_v1", "mode": "READ_ONLY",
               "snapshot_sha256": expected_sha256, "config_sha256": canonical_sha256(_POLICY), "status": "UNAVAILABLE",
               "reason_codes": [_text(reason, "reason", 128)], "data_kind": "UNKNOWN", "snapshot_id": None, "counts": {},
               "public_authority": False, "central_db_write": False, "public_apply": False}
    return FrozenCommunityKnowledge(_bytes(summary), b"{}")


def _source_view(view: Any) -> None:
    _obj(view, {"schema_version", "post_id", "fragments", "community", "as_of"}, "source_view")
    _enum(view["schema_version"], {SOURCE_VIEW_SCHEMA}, "source_view.schema_version")
    if type(view["post_id"]) is not int and not isinstance(view["post_id"], str):
        _fail("FIELD_INVALID", "post_id")
    if isinstance(view["post_id"], str):
        _text(view["post_id"], "post_id", 128)
    elif not -(2 ** 63) <= view["post_id"] < 2 ** 63:
        _fail("FIELD_INVALID", "post_id")
    fragments = view["fragments"]
    if type(fragments) is not list:
        _fail("FIELD_INVALID", "fragments")
    if len(fragments) > MAX_QUERY_FRAGMENTS:
        _fail("QUERY_FRAGMENT_LIMIT")
    seen, chars = set(), 0
    for fragment in fragments:
        _obj(fragment, {"raw_path", "kind", "text"}, "fragment")
        path = _text(fragment["raw_path"], "raw_path", 256)
        kind = _enum(fragment["kind"], {"TITLE", "BODY", "COMMENT"}, "kind")
        if not ((kind == "TITLE" and path == "/title") or (kind == "BODY" and _BODY_PATH.fullmatch(path)) or (kind == "COMMENT" and _COMMENT_PATH.fullmatch(path))):
            _fail("ORIGINAL_SOURCE_PATH_INVALID", path)
        if path in seen:
            _fail("DUPLICATE_SOURCE_PATH", path)
        seen.add(path)
        text = fragment["text"]
        if not isinstance(text, str):
            _fail("FIELD_INVALID", "fragment.text")
        text.encode("utf-8")
        chars += len(text)
        if chars > MAX_QUERY_CHARS:
            _fail("QUERY_CHARACTER_LIMIT")
    for key in ("community", "as_of"):
        ctx = _obj(view[key], {"value", "source_path", "status"}, key)
        _enum(ctx["status"], {"EXPLICIT", "UNKNOWN"}, key + ".status")
        _text(ctx["source_path"], key + ".source_path", 256, nullable=True)
        _text(ctx["value"], key + ".value", 128, nullable=True)
        if ctx["status"] == "EXPLICIT" and (ctx["value"] is None or not ctx["source_path"] or not ctx["source_path"].startswith("/")):
            _fail("CONTEXT_BINDING_MISSING", key)
    if view["as_of"]["status"] == "EXPLICIT":
        _date(view["as_of"]["value"], "as_of")


def _word(char: str) -> bool:
    return bool(char) and (char.isalnum() or char == "_" or unicodedata.category(char).startswith("M"))


def _matches(text: str, surface: str):
    start = 0
    while True:
        position = text.find(surface, start)
        if position < 0:
            return
        end = position + len(surface)
        if not _word(text[position - 1:position] if position else "") and not _word(text[end:end + 1]):
            yield position, end
        start = position + 1


def _eligibility(row: dict, source: dict, community: str, as_of: datetime, cutoff: datetime) -> str | None:
    if row["review_status"] == "REJECTED":
        return "CANDIDATE_REJECTED"
    rights = source["rights"]
    if rights["status"] not in {"REUSE_PERMITTED", "SYNTHETIC_FIXTURE"} or rights["takedown_status"] != "ACTIVE" or not rights["basis_ref"] or rights["reviewed_at"] is None or any(rights[k] is not True for k in ("collection", "retention", "derived_index", "quotation")):
        return "RIGHTS_NOT_ELIGIBLE"
    if not row["community_scope"] or not source["community_scope"]:
        return "SOURCE_COMMUNITY_UNKNOWN"
    if community not in row["community_scope"] or community not in source["community_scope"]:
        return "COMMUNITY_MISMATCH"
    if any(source[k] is None for k in ("source_published_at", "captured_at", "available_at")):
        return "SOURCE_TIME_UNKNOWN"
    if _date(source["available_at"], "available_at") > min(as_of, cutoff):
        return "SOURCE_NOT_YET_AVAILABLE"
    if _date(rights["reviewed_at"], "reviewed_at") > min(as_of, cutoff):
        return "RIGHTS_NOT_YET_REVIEWED"
    scope = row["temporal_scope"]
    if scope["valid_from"] is None:
        return "SENSE_TIME_UNKNOWN"
    if as_of < _date(scope["valid_from"], "valid_from") or (scope["valid_to"] is not None and as_of >= _date(scope["valid_to"], "valid_to")):
        return "SENSE_OUTSIDE_VALIDITY"
    return None


def _candidate_receipt(row: dict, refs: list, sources: dict, aliases: list, lexicon: list) -> dict:
    source_refs = []
    roots = set()
    for ref in refs:
        source = sources[ref["source_id"]]
        summary = dict(ref)
        for key in ("source_ref", "payload_byte_sha256", "source_published_at", "source_modified_at", "captured_at", "available_at", "time_unknown_reason", "community_scope", "lineage_root_id", "parent_id", "derivation_kind", "lineage_status"):
            summary[key] = source[key]
        summary["rights_status"] = source["rights"]["status"]
        source_refs.append(summary)
        if source["lineage_status"] == "DECLARED":
            roots.add(source["lineage_root_id"])
    def reviewed_entry(entry):
        copy = {key: value for key, value in entry.items() if key != "row_content_sha256"}
        copy["review"] = {key: value for key, value in entry["review"].items() if key != "receipt_ref"}
        return copy
    review = row.get("review", {"authority": "UNKNOWN", "reviewer": None, "receipt_sha256": None})
    eligible_aliases = [item for item in aliases if item["explicit_alias_assertion_ref"] in refs]
    return {"candidate_id": row["candidate_id"], "sense_id": row["sense_candidate_id"], "namespace": row["namespace"],
            "surface": row["surface_raw"], "definition": row["definition_text"], "review_status": row["review_status"],
            "review": {key: value for key, value in review.items() if key != "receipt_ref"}, "source_refs": source_refs,
            "community_scope": row["community_scope"], "temporal_scope": row["temporal_scope"],
            "work_alias_entries": [reviewed_entry(item) for item in eligible_aliases], "lexicon_entries": [reviewed_entry(item) for item in lexicon],
            "declared_lineage_roots": sorted(roots), "independent_support_count": None}


def _seal(receipt: dict) -> dict:
    receipt["receipt_digest_scope"] = "CANONICAL_EXCLUDING_ELAPSED_SELF_AND_STORAGE_BINDING"
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    if len(_bytes(receipt)) > MAX_RECEIPT_BYTES:
        receipt["candidates"] = []
        receipt["occurrences"] = []
        receipt["status"] = "LIMIT_EXCEEDED"
        receipt["reason_codes"] = ["RECEIPT_BYTE_LIMIT"]
        receipt["counts"]["returned_candidates"] = 0
        receipt["counts"]["returned_occurrences"] = 0
        del receipt["receipt_sha256"]
        receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


@dataclass(frozen=True, slots=True)
class FrozenCommunityKnowledge:
    _summary_json: bytes
    _bundle_json: bytes

    def summary(self) -> dict:
        return json.loads(self._summary_json)

    def query(self, source_view: Any) -> dict:
        summary = self.summary()
        post_id = source_view.get("post_id") if type(source_view) is dict else None
        if type(post_id) not in (int, str) or (isinstance(post_id, str) and len(post_id) > 128):
            post_id = None
        if isinstance(post_id, str):
            try:
                post_id.encode("utf-8")
            except UnicodeError:
                post_id = None
        if type(post_id) is int and not -(2 ** 63) <= post_id < 2 ** 63:
            post_id = None
        receipt = {"schema_version": RECEIPT_SCHEMA, "mode": "READ_ONLY", "post_id": post_id,
                   "status": "UNAVAILABLE", "reason_codes": list(summary["reason_codes"]),
                   "snapshot_sha256": summary["snapshot_sha256"], "query_sha256": None, "config_sha256": summary["config_sha256"],
                   "data_kind": summary["data_kind"], "evaluation_mode": "RETROSPECTIVE_SNAPSHOT_AS_OF_FILTERED",
                   "candidates": [], "occurrences": [], "excluded_counts": {}, "counts": {"matched_candidates": 0, "eligible_candidates": 0, "sense_count": 0, "occurrence_count": 0, "returned_candidates": 0, "returned_occurrences": 0},
                   "consumption": {"status": "QUERY_ONLY"}, "public_authority": False, "central_db_write": False, "public_apply": False}
        try:
            _source_view(source_view)
            # Hash a private JSON copy so caller-owned containers are never retained.
            query_bytes = _bytes(source_view)
            receipt["query_sha256"] = hashlib.sha256(query_bytes).hexdigest()
            view = json.loads(query_bytes)
        except (CommunityKnowledgeError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
            code = getattr(exc, "code", "QUERY_ENCODING_INVALID")
            receipt["status"] = "LIMIT_EXCEEDED" if code in {"QUERY_FRAGMENT_LIMIT", "QUERY_CHARACTER_LIMIT"} else "INVALID_INPUT"
            receipt["reason_codes"] = [code]
            return _seal(receipt)
        if summary["status"] == "UNAVAILABLE":
            return _seal(receipt)
        if any(view[key]["status"] != "EXPLICIT" for key in ("community", "as_of")):
            receipt["status"] = "UNRESOLVED_CONTEXT"
            receipt["reason_codes"] = [key.upper() + "_UNKNOWN" for key in ("community", "as_of") if view[key]["status"] != "EXPLICIT"]
            return _seal(receipt)
        bundle = json.loads(self._bundle_json)
        rows, sources = bundle["candidates"], bundle["sources"]
        surfaces = sorted({row["surface_raw"] for row in rows})
        if len(surfaces) * len(view["fragments"]) > MAX_COMPARISONS:
            receipt["status"], receipt["reason_codes"] = "LIMIT_EXCEEDED", ["QUERY_COMPARISON_LIMIT"]
            return _seal(receipt)
        as_of = _date(view["as_of"]["value"], "as_of")
        cutoff = _date(bundle["manifest"]["freeze_cutoff"], "freeze_cutoff")
        occurrences = []
        matched_surfaces = set()
        # Count all bounded-input occurrences, retain at most the explicit cap.
        occurrence_count = 0
        for fragment in view["fragments"]:
            for surface in surfaces:
                for start, end in _matches(fragment["text"], surface):
                    occurrence_count += 1
                    matched_surfaces.add(surface)
                    if len(occurrences) < MAX_OCCURRENCES:
                        occurrences.append({"raw_path": fragment["raw_path"], "kind": fragment["kind"], "surface": surface,
                                            "character_span_start": start, "character_span_end": end,
                                            "utf8_byte_span_start": len(fragment["text"][:start].encode("utf-8")),
                                            "utf8_byte_span_end": len(fragment["text"][:end].encode("utf-8")), "sense_ids": []})
        excluded = Counter()
        candidates, by_surface = [], {}
        for row in rows:
            if row["surface_raw"] not in matched_surfaces:
                continue
            receipt["counts"]["matched_candidates"] += 1
            eligible = []
            for ref in row["source_refs"]:
                reason = _eligibility(row, sources[ref["source_id"]], view["community"]["value"], as_of, cutoff)
                if reason is None:
                    eligible.append(ref)
                else:
                    excluded[reason] += 1
            if eligible:
                candidates.append(_candidate_receipt(row, eligible, sources, bundle["aliases"].get(row["candidate_id"], []), bundle["lexicon"].get(row["candidate_id"], [])))
                by_surface.setdefault(row["surface_raw"], set()).add(row["sense_candidate_id"])
        senses = {candidate["sense_id"] for candidate in candidates}
        receipt["excluded_counts"] = dict(sorted(excluded.items()))
        receipt["counts"].update(eligible_candidates=len(candidates), sense_count=len(senses), occurrence_count=occurrence_count)
        if occurrence_count > MAX_OCCURRENCES or len(senses) > MAX_SENSES:
            receipt["status"] = "LIMIT_EXCEEDED"
            receipt["reason_codes"] = (["OCCURRENCE_LIMIT"] if occurrence_count > MAX_OCCURRENCES else []) + (["SENSE_LIMIT"] if len(senses) > MAX_SENSES else [])
            return _seal(receipt)
        for occurrence in occurrences:
            occurrence["sense_ids"] = sorted(by_surface.get(occurrence["surface"], set()))
        receipt["candidates"], receipt["occurrences"] = candidates, occurrences
        receipt["counts"].update(returned_candidates=len(candidates), returned_occurrences=len(occurrences))
        unresolved = any(key in excluded for key in ("SOURCE_TIME_UNKNOWN", "SOURCE_COMMUNITY_UNKNOWN", "SENSE_TIME_UNKNOWN"))
        receipt["status"] = "AMBIGUOUS" if any(len(value) > 1 for value in by_surface.values()) else ("UNRESOLVED_CONTEXT" if unresolved else ("OK" if candidates else "NO_MATCH"))
        receipt["reason_codes"] = ["MULTIPLE_ELIGIBLE_SENSES"] if receipt["status"] == "AMBIGUOUS" else (["ELIGIBILITY_UNKNOWN"] if receipt["status"] == "UNRESOLVED_CONTEXT" else [])
        return _seal(receipt)
