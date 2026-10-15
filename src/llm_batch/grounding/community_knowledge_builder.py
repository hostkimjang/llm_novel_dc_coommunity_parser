"""로컬 capture 바이트를 중립 관측과 새 커뮤니티 snapshot으로 묶는다."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
from typing import Any, Mapping
import uuid

from . import p0_source_profile_raw_parser_core as parser_core
from .p0_source_profile_raw_parser_core_parent_validator import validate_result_against_capture


CAPTURE_SCHEMA = "community_knowledge_capture_manifest_v1"
REVIEW_SCHEMA = "community_knowledge_classification_review_v1"
BUILDER_VERSION = "local_capture_neutral_builder_v1"
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_METADATA_BYTES = 256 * 1024
MAX_CAPTURES = 100
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class CommunityKnowledgeBuildError(ValueError):
    """실패 코드를 보존하며 원본이나 기존 output을 덮지 않는다."""
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.failure_directory: str | None = None
        super().__init__(f"{code}: {detail}" if detail else code)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw: bytes, label: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CommunityKnowledgeBuildError("DUPLICATE_JSON_KEY", label)
            result[key] = value
        return result
    def constant(value):
        raise CommunityKnowledgeBuildError("NONFINITE_JSON", label)
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CommunityKnowledgeBuildError("INVALID_JSON", label) from exc


def _object(value: Any, required: set[str], label: str, *, optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - optional:
        raise CommunityKnowledgeBuildError("INVALID_SCHEMA", label)
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 4096:
        raise CommunityKnowledgeBuildError("INVALID_TEXT", label)
    return value


def _timestamp(value: Any, label: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    try:
        parsed = datetime.fromisoformat(_text(value, label).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone required")
        return parsed
    except (ValueError, TypeError) as exc:
        raise CommunityKnowledgeBuildError("INVALID_TIME", label) from exc


def _no_links(path: Path) -> None:
    """해석 전에 각 기존 경로의 symlink와 Windows reparse point를 거부한다."""
    for item in (path, *path.parents):
        if not item.exists() and not item.is_symlink():
            continue
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise CommunityKnowledgeBuildError("SYMLINK_OR_REPARSE_FORBIDDEN", str(item))


def _root(path: str | Path) -> Path:
    value = Path(os.path.abspath(path))
    _no_links(value)
    if not value.is_dir():
        raise CommunityKnowledgeBuildError("ROOT_NOT_DIRECTORY", str(value))
    return value.resolve(strict=True)


def _within(path: Path, root: Path, *, must_exist: bool = True) -> Path:
    value = Path(os.path.abspath(path))
    _no_links(value)
    resolved = value.resolve(strict=must_exist)
    if resolved == root or not resolved.is_relative_to(root):
        raise CommunityKnowledgeBuildError("PATH_ESCAPE", str(value))
    return resolved


def _read(path: Path, limit: int) -> bytes:
    _no_links(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise CommunityKnowledgeBuildError("SOURCE_NOT_REGULAR_FILE", str(path))
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise CommunityKnowledgeBuildError("SOURCE_BYTE_LIMIT", str(path))
    _no_links(path)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise CommunityKnowledgeBuildError("SOURCE_CHANGED_DURING_READ", str(path))
    return raw


def _read_ref(ref: Any, capture_root: Path, sources: list[dict], *, role: str, limit: int) -> tuple[bytes, dict]:
    _object(ref, {"path", "sha256"}, role)
    path_text = _text(ref["path"], role + ".path")
    path = Path(path_text)
    if path.is_absolute() or path.drive or ".." in path.parts or ":" in path_text:
        raise CommunityKnowledgeBuildError("SOURCE_PATH_NOT_RELATIVE", path_text)
    if not isinstance(ref["sha256"], str) or not SHA_RE.fullmatch(ref["sha256"]):
        raise CommunityKnowledgeBuildError("INVALID_SHA256", role)
    resolved = _within(capture_root / path, capture_root)
    raw = _read(resolved, limit)
    if _sha(raw) != ref["sha256"]:
        raise CommunityKnowledgeBuildError("SOURCE_SHA256_MISMATCH", role)
    record = {"path": str(resolved), "sha256": ref["sha256"], "bytes": len(raw), "role": role}
    sources.append(record)
    return raw, record


def _verify_sources(sources: list[dict]) -> list[dict]:
    receipts = []
    for source in sources:
        raw = _read(Path(source["path"]), max(MAX_MANIFEST_BYTES, source["bytes"]))
        after = _sha(raw)
        if after != source["sha256"] or len(raw) != source["bytes"]:
            raise CommunityKnowledgeBuildError("SOURCE_CHANGED_DURING_BUILD", source["path"])
        receipts.append({"path": source["path"], "sha256_start": source["sha256"], "sha256_end": after, "unchanged": True})
    return receipts


def _write_new(path: Path, raw: bytes) -> dict:
    _no_links(path.parent)
    with path.open("xb") as target:
        target.write(raw)
        target.flush()
        os.fsync(target.fileno())
    return {"path": path.name, "sha256": _sha(raw), "bytes": len(raw)}


def _review(ref: dict, source: dict, capture_root: Path, sources: list[dict]) -> tuple[dict, bytes, str]:
    raw, _ = _read_ref(ref, capture_root, sources, role="classification_review", limit=MAX_METADATA_BYTES)
    value = _object(_strict_json(raw, "review"), {"schema_version", "source_id", "payload_byte_sha256", "observation_sha256",
                    "review_status", "authority", "reviewer", "sense_candidate_id", "classification"}, "review")
    if (value["schema_version"] != REVIEW_SCHEMA or value["source_id"] != source["source_id"] or
            value["payload_byte_sha256"] != source["payload_byte_sha256"]):
        raise CommunityKnowledgeBuildError("REVIEW_SOURCE_BINDING_MISMATCH")
    if not isinstance(value["observation_sha256"], str) or not SHA_RE.fullmatch(value["observation_sha256"]):
        raise CommunityKnowledgeBuildError("REVIEW_OBSERVATION_SHA_INVALID")
    if value["review_status"] not in {"REVIEWED", "REJECTED"}:
        raise CommunityKnowledgeBuildError("REVIEW_STATUS_INVALID")
    if value["authority"] not in {"HUMAN_REVIEW", "MODEL_REFERENCE", "SYNTHETIC_FIXTURE", "UNKNOWN"}:
        raise CommunityKnowledgeBuildError("REVIEW_AUTHORITY_INVALID")
    if value["reviewer"] is not None:
        _text(value["reviewer"], "reviewer")
    _text(value["sense_candidate_id"], "sense_candidate_id")
    classification = value["classification"]
    if not isinstance(classification, dict):
        raise CommunityKnowledgeBuildError("REVIEW_CLASSIFICATION_INVALID")
    namespace = classification.get("namespace")
    fields = {"candidate_ledger": {"namespace"},
              "work_alias_registry": {"namespace", "work_id", "edition_id", "media_type", "canonical_title", "canonical_title_locator"},
              "community_lexicon": {"namespace", "term_kind", "competing_sense_ids"}}
    if namespace not in fields:
        raise CommunityKnowledgeBuildError("REVIEW_NAMESPACE_INVALID")
    _object(classification, fields[namespace], "classification")
    if value["review_status"] == "REJECTED" and namespace != "candidate_ledger":
        raise CommunityKnowledgeBuildError("REJECTED_CLASSIFICATION_CANNOT_ENTER_REGISTRY")
    name = "reviews/" + _sha(raw) + ".json"
    return value, raw, name


def _prepare(spec_path: Path, capture_root: Path) -> tuple[dict, dict, dict, list[dict], list[dict]]:
    """출력 쓰기 전 바이트·중립 parser·명시 검토만 구성한다."""
    raw_spec = _read(spec_path, MAX_MANIFEST_BYTES)
    spec = _object(_strict_json(raw_spec, "capture manifest"),
                   {"schema_version", "snapshot_id", "data_kind", "built_at", "freeze_cutoff", "captures"}, "capture manifest")
    if spec["schema_version"] != CAPTURE_SCHEMA or spec["data_kind"] not in {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}:
        raise CommunityKnowledgeBuildError("CAPTURE_SCHEMA_INVALID")
    _text(spec["snapshot_id"], "snapshot_id")
    built = _timestamp(spec["built_at"], "built_at")
    freeze = _timestamp(spec["freeze_cutoff"], "freeze_cutoff")
    if freeze > built:
        raise CommunityKnowledgeBuildError("FREEZE_AFTER_BUILD")
    if not isinstance(spec["captures"], list) or len(spec["captures"]) > MAX_CAPTURES:
        raise CommunityKnowledgeBuildError("CAPTURE_COUNT_LIMIT")
    sources = [{"path": str(spec_path), "sha256": _sha(raw_spec), "bytes": len(raw_spec), "role": "capture_manifest"}]
    # These helpers are the store owner's canonical record contract.
    from .community_knowledge import candidate_id_for, row_content_sha256
    rows = {"candidate_ledger": [], "work_alias_registry": [], "community_lexicon": []}
    inventory, capture_inventory, files, seen = [], [], {}, set()
    for capture in spec["captures"]:
        _object(capture, {"source", "content_type", "temporal_scope", "reviews"}, "capture")
        source = deepcopy(_object(capture["source"], {
            "source_id", "source_ref", "payload_ref", "payload_byte_sha256", "capture_profile", "capture_version", "normalization_version",
            "source_published_at", "source_modified_at", "captured_at", "available_at", "time_unknown_reason", "community_scope",
            "lineage_root_id", "parent_id", "derivation_kind", "lineage_status", "rights"}, "capture.source"))
        sid = _text(source["source_id"], "source_id")
        if sid in seen:
            raise CommunityKnowledgeBuildError("DUPLICATE_SOURCE_ID", sid)
        seen.add(sid)
        rights = _object(source["rights"], {"status", "basis_ref", "basis_sha256", "collection", "retention", "derived_index", "quotation", "reviewed_at", "takedown_status"}, "rights")
        if rights["status"] not in {"REUSE_PERMITTED", "SYNTHETIC_FIXTURE", "UNKNOWN", "REVOKED"}:
            raise CommunityKnowledgeBuildError("RIGHTS_STATUS_INVALID", sid)
        for flag in ("collection", "retention", "derived_index", "quotation"):
            if rights[flag] is not None and type(rights[flag]) is not bool:
                raise CommunityKnowledgeBuildError("RIGHTS_PERMISSION_INVALID", sid)
        if rights["takedown_status"] not in {"ACTIVE", "UNKNOWN", "REQUESTED", "REMOVED"}:
            raise CommunityKnowledgeBuildError("TAKEDOWN_STATUS_INVALID", sid)
        if spec["data_kind"] == "SOURCE_BACKED" and rights["status"] == "SYNTHETIC_FIXTURE":
            raise CommunityKnowledgeBuildError("SYNTHETIC_RIGHTS_IN_SOURCE_BACKED", sid)
        basis, basis_record = b"", None
        if rights["basis_ref"] is not None or rights["basis_sha256"] is not None:
            basis, basis_record = _read_ref({"path": rights["basis_ref"], "sha256": rights["basis_sha256"]}, capture_root, sources, role="rights_basis", limit=MAX_METADATA_BYTES)
        payload, payload_record = _read_ref({"path": source["payload_ref"], "sha256": source["payload_byte_sha256"]}, capture_root, sources, role="capture_payload", limit=parser_core.MAX_PAYLOAD_BYTES)
        status = {"source_id": sid, "payload_byte_sha256": payload_record["sha256"], "rights_basis_sha256": basis_record["sha256"] if basis_record else None,
                  "source_metadata": deepcopy(source), "disposition": "NOT_PARSED", "reason_codes": [], "observations": 0,
                  "active_query_eligible": False, "eligibility_scope": "CAPTURE_GATES_ONLY_REQUIRES_POST_QUERY"}
        capture_inventory.append(status)
        rights_ok = (basis_record is not None and rights["status"] in {"REUSE_PERMITTED", "SYNTHETIC_FIXTURE"} and rights["takedown_status"] == "ACTIVE" and
                     all(rights[flag] is True for flag in ("collection", "retention", "derived_index", "quotation")))
        if not rights_ok:
            status.update(disposition="EXCLUDED_RIGHTS", reason_codes=["RIGHTS_REVOKED" if rights["status"] == "REVOKED" or rights["takedown_status"] in {"REQUESTED", "REMOVED"} else "RIGHTS_UNKNOWN_OR_NOT_PERMITTED"])
            # No raw payload, definition, or derivative is copied for excluded rights.
            continue
        unknown_time = False
        for key in ("source_published_at", "source_modified_at", "captured_at", "available_at"):
            _timestamp(source[key], key, nullable=True)
            if key != "source_modified_at" and source[key] is None:
                unknown_time = True
        if unknown_time:
            _text(source["time_unknown_reason"], "time_unknown_reason")
            status["reason_codes"].append("TIME_UNKNOWN")
        temporal = _object(capture["temporal_scope"], {"valid_from", "valid_to", "time_unknown_reason"}, "temporal_scope")
        for key in ("valid_from", "valid_to"):
            _timestamp(temporal[key], key, nullable=True)
        reviewed_at = _timestamp(rights["reviewed_at"], "rights.reviewed_at", nullable=True)
        if reviewed_at is None:
            status["reason_codes"].append("RIGHTS_REVIEW_TIME_UNKNOWN")
        elif reviewed_at > freeze:
            status["reason_codes"].append("RIGHTS_REVIEW_AFTER_FREEZE_CUTOFF")
        if temporal["valid_from"] is None:
            status["reason_codes"].append("SENSE_TIME_UNKNOWN")
        _text(capture["content_type"], "content_type")
        envelope = {"source_profile": source["capture_profile"], "content_type": capture["content_type"],
                    "capture_version": source["capture_version"], "normalization_version": source["normalization_version"]}
        try:
            parsed = parser_core.parse_capture(payload=payload, **envelope)
            replay = validate_result_against_capture(parsed, payload=payload, **envelope)
        except ValueError as exc:
            raise CommunityKnowledgeBuildError("NEUTRAL_PARSER_REPLAY_FAILED", sid) from exc
        status.update(disposition=parsed["disposition"], observations=parsed["observation_count"],
                      parser_result_sha256=parsed["result_sha256"], parent_replay_receipt_sha256=replay["receipt_sha256"])
        if parsed["disposition"] != "MATCHED":
            status["reason_codes"].append(parsed["reason_code"])
        status["active_query_eligible"] = (parsed["disposition"] == "MATCHED" and not unknown_time and bool(source["community_scope"]) and
                                           reviewed_at is not None and reviewed_at <= freeze and temporal["valid_from"] is not None and
                                           _timestamp(source["available_at"], "available_at", nullable=True) <= freeze)
        if source["available_at"] is not None and _timestamp(source["available_at"], "available_at") > freeze:
            status["reason_codes"].append("AFTER_FREEZE_CUTOFF")
        if not source["community_scope"]:
            status["reason_codes"].append("COMMUNITY_UNKNOWN")
        token = _sha(sid.encode("utf-8"))
        source["payload_ref"] = "payloads/" + token + ".bin"
        rights["basis_ref"] = "rights/" + _sha(basis) + ".bin"
        files[source["payload_ref"]] = payload
        files[rights["basis_ref"]] = basis
        inventory.append(source)
        files["parser/" + token + ".json"] = _json_bytes({"result": parsed, "validation": replay}) + b"\n"
        if not isinstance(capture["reviews"], list):
            raise CommunityKnowledgeBuildError("REVIEWS_NOT_LIST", sid)
        reviews = {}
        for ref in capture["reviews"]:
            reviewed, review_raw, review_path = _review(ref, source, capture_root, sources)
            observation_sha = reviewed["observation_sha256"]
            if observation_sha in reviews:
                raise CommunityKnowledgeBuildError("DUPLICATE_OBSERVATION_REVIEW", sid)
            if reviewed["authority"] == "SYNTHETIC_FIXTURE" and spec["data_kind"] != "SYNTHETIC_FIXTURE":
                raise CommunityKnowledgeBuildError("SYNTHETIC_REVIEW_IN_SOURCE_BACKED", sid)
            reviews[observation_sha] = (reviewed, review_path, _sha(review_raw))
            files[review_path] = review_raw
        matched_reviews = set()
        for observation in parsed["observations"]:
            source_ref = {key: observation[key] for key in ("utf8_byte_span_start", "utf8_byte_span_end", "evidence_text", "evidence_utf8_sha256")}
            source_ref["source_id"] = sid
            entry = {"schema_version": "community_knowledge_candidate_v1", "namespace": "neutral_observation",
                     "surface_raw": observation["surface_text"], "surface_normalized": unicodedata.normalize("NFC", observation["surface_text"]),
                     "sense_candidate_id": "sense:" + _sha(_json_bytes({"source_id": sid, "observation_sha256": observation["observation_sha256"]})),
                     "definition_text": observation["presented_definition_text"], "relation_type": observation["relation_kind"],
                     "review_status": "UNREVIEWED", "community_scope": deepcopy(source["community_scope"]),
                     "temporal_scope": deepcopy(temporal), "source_refs": [source_ref]}
            review_record = reviews.get(observation["observation_sha256"])
            classification = None
            if review_record:
                matched_reviews.add(observation["observation_sha256"])
                reviewed, review_path, review_sha = review_record
                entry["sense_candidate_id"] = reviewed["sense_candidate_id"]
                entry["review_status"] = reviewed["review_status"]
                entry["review"] = {"authority": reviewed["authority"], "reviewer": reviewed["reviewer"], "receipt_ref": review_path, "receipt_sha256": review_sha}
                classification = reviewed["classification"]
            entry["candidate_id"] = candidate_id_for(entry)
            entry["row_content_sha256"] = row_content_sha256(entry)
            rows["candidate_ledger"].append(entry)
            if classification and classification["namespace"] == "work_alias_registry":
                alias = {key: deepcopy(value) for key, value in classification.items() if key != "namespace"}
                alias.update(schema_version="community_knowledge_work_alias_v1", registry_entry_id="alias:" + _sha(_json_bytes(classification) + entry["candidate_id"].encode()),
                             candidate_id=entry["candidate_id"], review=deepcopy(entry["review"]), explicit_alias_assertion_ref=deepcopy(source_ref))
                alias["row_content_sha256"] = row_content_sha256(alias)
                rows["work_alias_registry"].append(alias)
            elif classification and classification["namespace"] == "community_lexicon":
                lexicon = {"schema_version": "community_knowledge_lexicon_v1", "lexicon_entry_id": "lexicon:" + _sha(_json_bytes(classification) + entry["candidate_id"].encode()),
                           "candidate_id": entry["candidate_id"], "sense_id": entry["sense_candidate_id"], "definition": entry["definition_text"],
                           "term_kind": classification["term_kind"], "competing_sense_ids": deepcopy(classification["competing_sense_ids"]),
                           "community_scope": deepcopy(entry["community_scope"]), "temporal_scope": deepcopy(temporal), "review": deepcopy(entry["review"])}
                lexicon["row_content_sha256"] = row_content_sha256(lexicon)
                rows["community_lexicon"].append(lexicon)
        if matched_reviews != set(reviews):
            raise CommunityKnowledgeBuildError("REVIEW_OBSERVATION_NOT_BOUND", sid)
    if sum(len(items) for items in rows.values()) > 1000:
        raise CommunityKnowledgeBuildError("SNAPSHOT_ROW_LIMIT")
    files["source_inventory.json"] = _json_bytes({"schema_version": "community_knowledge_source_inventory_v1", "sources": inventory}) + b"\n"
    for name, items in rows.items():
        files[name + ".jsonl"] = b"".join(_json_bytes(row) + b"\n" for row in items)
    return spec, rows, files, sources, capture_inventory


def build_snapshot(local_capture_manifest: str | Path, output_directory: str | Path, *,
                   capture_root: str | Path, output_root: str | Path) -> dict:
    """새 폴더의 완성된 snapshot만 공개한다. 실패 stage는 명시적으로 남긴다."""
    source_root, destination_root = _root(capture_root), _root(output_root)
    spec_path = _within(Path(local_capture_manifest), source_root)
    output = _within(Path(output_directory), destination_root, must_exist=False)
    if output.exists():
        raise CommunityKnowledgeBuildError("OUTPUT_EXISTS", str(output))
    if not output.parent.is_dir():
        raise CommunityKnowledgeBuildError("OUTPUT_PARENT_MISSING", str(output.parent))
    spec, rows, files, sources, capture_inventory = _prepare(spec_path, source_root)
    if any(Path(source["path"]).is_relative_to(output) for source in sources):
        raise CommunityKnowledgeBuildError("OUTPUT_OVERLAPS_INPUT")
    _verify_sources(sources)
    from .community_knowledge import load_snapshot
    stage = output.parent / (".r3-build-" + uuid.uuid4().hex)
    stage.mkdir()
    try:
        for directory in ("payloads", "rights", "reviews", "parser"):
            (stage / directory).mkdir()
        if sum(len(raw) for name, raw in files.items() if not name.startswith("parser/")) > 4 * 1024 * 1024:
            raise CommunityKnowledgeBuildError("SNAPSHOT_BYTE_LIMIT")
        for name, raw in sorted(files.items()):
            _write_new(stage / name, raw)
        manifest = {"schema_version": "community_knowledge_snapshot_v1", "snapshot_id": spec["snapshot_id"], "data_kind": spec["data_kind"],
                    "built_at": spec["built_at"], "freeze_cutoff": spec["freeze_cutoff"], "parser_version": parser_core.CORE_VERSION,
                    "normalization_version": parser_core.SUPPORTED_NORMALIZATION_VERSION, "query_policy_version": "community_exact_surface_v1",
                    "rights_policy_version": "local_asserted_reuse_v1", "lineage_policy_version": "declared_root_no_independent_authority_v1", "files": {}}
        for name, items in rows.items():
            manifest["files"][name] = {"path": name + ".jsonl", "sha256": _sha(files[name + ".jsonl"]), "rows": len(items)}
        source_inventory = _strict_json(files["source_inventory.json"], "generated inventory")
        manifest["files"]["source_inventory"] = {"path": "source_inventory.json", "sha256": _sha(files["source_inventory.json"]), "source_count": len(source_inventory["sources"])}
        manifest_raw = _json_bytes(manifest) + b"\n"
        manifest_sha = _sha(manifest_raw)
        # Validate an explicitly provisional name; manifest.json is the final marker.
        provisional = stage / "manifest.provisional.json"
        _write_new(provisional, manifest_raw)
        frozen = load_snapshot(provisional, expected_sha256=manifest_sha)
        verified = _verify_sources(sources)
        receipt = {"schema_version": "community_knowledge_build_receipt_v1", "builder_version": BUILDER_VERSION,
                   "status": "COMPLETE_WITH_LIMITS" if any(item["reason_codes"] for item in capture_inventory) else "COMPLETE",
                   "data_kind": spec["data_kind"], "snapshot_id": spec["snapshot_id"], "snapshot_sha256": manifest_sha,
                   "output_manifest": str(output / "manifest.json"), "source_count": len(capture_inventory),
                   "snapshot_source_count": len(source_inventory["sources"]), "row_counts": {name: len(items) for name, items in rows.items()},
                   "capture_inventory": capture_inventory, "source_integrity": verified, "store_validation": frozen.summary(),
                   "parser_source_sha256": _sha(Path(parser_core.__file__).read_bytes()), "builder_source_sha256": _sha(Path(__file__).read_bytes()),
                   "public_authority": False, "central_db_write": False, "model_calls": 0, "network_calls": 0,
                   "actual_semantic_evidence_verified": False, "rights_authority_independently_verified": False}
        _write_new(stage / "build_receipt.json", _json_bytes(receipt) + b"\n")
        _no_links(output.parent)
        if output.exists():
            raise CommunityKnowledgeBuildError("OUTPUT_EXISTS", str(output))
        provisional.rename(stage / "manifest.json")
        stage.rename(output)
        return receipt
    except Exception as exc:
        failure = {"schema_version": "community_knowledge_build_failure_v1", "status": "FAILED_NOT_PUBLISHED",
                   "code": getattr(exc, "code", type(exc).__name__), "intended_output": str(output), "snapshot_published": False}
        # Remove only our marker, never recursively delete anything or touch inputs.
        marker = stage / "manifest.json"
        if marker.is_file() and not marker.is_symlink():
            marker.unlink()
        try:
            _write_new(stage / "FAILED_BUILD.json", _json_bytes(failure) + b"\n")
        except OSError:
            pass
        error = exc if isinstance(exc, CommunityKnowledgeBuildError) else CommunityKnowledgeBuildError("BUILD_VALIDATION_FAILED", str(exc))
        error.failure_directory = str(stage)
        if error is exc:
            raise
        raise error from exc
