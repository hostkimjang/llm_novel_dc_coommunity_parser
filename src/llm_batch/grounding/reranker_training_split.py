"""Pure validation of declared training exposure; no label inference or training.

Bytes supplied by the caller verify local binding, not the truth of source,
rights, work identity or annotation assertions. Legacy calibration stays intact.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA_VERSION = "reranker_training_split_v1"
POLICY_VERSION = "all_exposed_identity_groups_v1"
SPLITS = ("TRAIN", "DEV", "CALIBRATION", "FROZEN_HOLDOUT")
MAX_ROWS = 1000
MAX_SOURCES = 4000
MAX_BYTES = 8 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ASSIGNMENT = {"example_id", "post_id", "split_group_id", "content_fingerprint", "source_group_fingerprint", "split", "truth_kind", "truth_label", "label_provenance_sha256", "candidate_set_fingerprint", "gold_work_fingerprint", "binding_status", "matched_candidate_ids"}
_SPAN = {"source_id", "raw_path", "utf8_byte_span_start", "utf8_byte_span_end", "text", "span_sha256"}
_EXPOSURE = {"candidate_id", "corpus_candidate_id", "polarity", "work_id", "edition_id", "media_type", "alias_family_ids", "source_ids"}


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def seal_manifest(payload: Mapping[str, Any]) -> dict:
    result = deepcopy(dict(payload))
    result.pop("manifest_sha256", None)
    result["manifest_sha256"] = canonical_sha256(result)
    return result


class _Invalid(ValueError):
    def __init__(self, code: str, path: str):
        self.code, self.path = code, path
        super().__init__(code + ": " + path)


def _require(condition: bool, code: str, path: str) -> None:
    if not condition:
        raise _Invalid(code, path)


def _obj(value: Any, fields: set, path: str) -> dict:
    _require(type(value) is dict and set(value) == fields, "SCHEMA_INVALID", path)
    return value


def _text(value: Any, path: str, nullable=False) -> Any:
    if nullable and value is None:
        return None
    _require(isinstance(value, str) and bool(value.strip()) and len(value) <= 512 and "\x00" not in value, "TEXT_INVALID", path)
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise _Invalid("TEXT_INVALID", path) from exc
    return value


def _sha(value: Any, path: str, nullable=False) -> Any:
    if nullable and value is None:
        return None
    _require(isinstance(value, str) and _SHA.fullmatch(value) is not None, "SHA_INVALID", path)
    return value


def _enum(value: Any, choices: set, path: str) -> str:
    _require(isinstance(value, str) and value in choices, "ENUM_INVALID", path)
    return value


def _list(value: Any, path: str, maximum: int) -> list:
    _require(type(value) is list and len(value) <= maximum, "LIST_OR_LIMIT_INVALID", path)
    return value


def _ids(value: Any, path: str, maximum=256) -> list:
    result = _list(value, path, maximum)
    for item in result:
        _text(item, path)
    _require(len(result) == len(set(result)), "DUPLICATE_ID", path)
    return result


def calibration_assignments(manifest: Mapping[str, Any]) -> list[dict]:
    """Project explicit assignments only; never upgrade unknown truth or IDs."""
    return [deepcopy(row["assignment"]) for row in manifest["rows"] if row["assignment"]["split"] != "TRAIN"]


class _Validator:
    def __init__(self, source_payloads: Mapping, evidence_payloads: Mapping):
        self.payloads = source_payloads
        self.evidence = evidence_payloads
        self.issues: list[dict] = []
        self.sources: dict[str, dict] = {}
        self.groups: dict[tuple, tuple] = {}
        self.identity: dict[str, dict] = {}
        self.corpus_identity: dict[str, dict] = {}
        self.examples: set[str] = set()
        self.coordinates: set[tuple] = set()
        self.counts = {split: {"rows": 0, "unique_posts": 0, "candidates": 0, "positive": 0, "negative": 0, "unjudged_exposures": 0, "unjudged_rows": 0} for split in SPLITS}
        self.posts = {split: set() for split in SPLITS}
        self.grades: Counter = Counter()
        self.kind = "UNKNOWN"

    def issue(self, severity: str, code: str, path: str, **details):
        self.issues.append({"severity": severity, "code": code, "path": path, **details})

    def missing(self, condition: bool, code: str, path: str):
        if condition:
            self.issue("MISSING", code, path)

    def leak(self, kind: str, value: Any, row: dict):
        if value is None:
            return
        key = (kind, value)
        current = (row["split"], row["example_id"])
        previous = self.groups.setdefault(key, current)
        if previous[0] != current[0]:
            self.issue("ERROR", "CROSS_SPLIT_EXPOSURE", row["example_id"], dimension=kind,
                       value=value, first_split=previous[0], first_example=previous[1], second_split=current[0])

    def evidence_ref(self, sha: Any, path: str):
        _sha(sha, path, nullable=True)
        if sha is None:
            self.issue("MISSING", "EVIDENCE_SHA_MISSING", path)
        elif sha not in self.evidence:
            self.issue("MISSING", "EVIDENCE_BYTES_MISSING", path)
        else:
            _require(hashlib.sha256(self.evidence[sha]).hexdigest() == sha, "EVIDENCE_SHA_MISMATCH", path)

    def unique_corpus_binding(self, corpus_id: str, exposure: dict, assignment: dict):
        # UNIQUE is a manifest-wide assertion. Unknown fields do not erase or
        # invent identity, and ambiguous proposals never enter this registry.
        previous = self.corpus_identity.setdefault(corpus_id, {})
        for field in ("candidate_id", "work_id", "edition_id", "media_type"):
            known = exposure[field]
            if known is None:
                continue
            origin = previous.setdefault(field, (known, assignment["example_id"], assignment["split"]))
            if origin[0] != known:
                self.issue("ERROR", "R2_UNIQUE_BRIDGE_CONFLICT", assignment["example_id"],
                           corpus_candidate_id=corpus_id, dimension=field,
                           first_value=origin[0], second_value=known,
                           first_example=origin[1], second_example=assignment["example_id"],
                           first_split=origin[2], second_split=assignment["split"])

    def provenance(self, value: Any, path: str, scope: str) -> dict:
        item = _obj(value, {"grade", "artifact_sha256", "reviewer", "scope"}, path)
        grade = _enum(item["grade"], {"MODEL_REFERENCE", "GOLD_LITE", "HUMAN_GOLD", "SYNTHETIC_FIXTURE", "UNJUDGED"}, path + ".grade")
        _require(item["scope"] == scope, "PROVENANCE_SCOPE_MISMATCH", path)
        _require(not (grade == "SYNTHETIC_FIXTURE" and self.kind != "SYNTHETIC_FIXTURE"), "SYNTHETIC_PROVENANCE_MIXED", path)
        _text(item["reviewer"], path + ".reviewer", nullable=True)
        self.missing(item["reviewer"] is None, "REVIEWER_MISSING", path)
        self.missing(grade == "UNJUDGED", "PROVENANCE_UNJUDGED", path)
        self.evidence_ref(item["artifact_sha256"], path + ".artifact_sha256")
        self.grades[grade] += 1
        return item

    def source(self, value: Any):
        row = _obj(value, {"source_id", "payload_sha256", "source_group_id", "lineage_root_id", "rights_status"}, "source")
        sid = _text(row["source_id"], "source.source_id")
        _require(sid not in self.sources, "DUPLICATE_SOURCE_ID", sid)
        _sha(row["payload_sha256"], sid + ".payload_sha256")
        for field in ("source_group_id", "lineage_root_id"):
            _text(row[field], sid + "." + field, nullable=True)
            self.missing(row[field] is None, "SOURCE_GROUP_UNKNOWN", sid + "." + field)
        rights = _enum(row["rights_status"], {"REUSE_PERMITTED", "SYNTHETIC_FIXTURE", "UNKNOWN", "REVOKED"}, sid + ".rights_status")
        _require(rights != "REVOKED", "RIGHTS_REVOKED", sid)
        _require(not (rights == "SYNTHETIC_FIXTURE" and self.kind != "SYNTHETIC_FIXTURE"), "SYNTHETIC_PROVENANCE_MIXED", sid)
        self.missing(rights == "UNKNOWN", "RIGHTS_UNKNOWN", sid)
        self.missing(sid not in self.payloads, "SOURCE_BYTES_MISSING", sid)
        if sid in self.payloads:
            _require(hashlib.sha256(self.payloads[sid]).hexdigest() == row["payload_sha256"], "SOURCE_SHA_MISMATCH", sid)
        self.sources[sid] = row

    def span(self, value: Any, source_ids: list, path: str):
        item = _obj(value, _SPAN, path)
        sid = _text(item["source_id"], path + ".source_id")
        _require(sid in source_ids and sid in self.sources, "SPAN_SOURCE_NOT_BOUND", path)
        raw_path = _text(item["raw_path"], path + ".raw_path")
        _require(raw_path.startswith("/"), "RAW_PATH_INVALID", path)
        start, end = item["utf8_byte_span_start"], item["utf8_byte_span_end"]
        _require(type(start) is int and type(end) is int and 0 <= start < end <= MAX_BYTES, "SOURCE_SPAN_INVALID", path)
        text = item["text"]
        _require(isinstance(text, str) and len(text) <= 12000, "SOURCE_SPAN_TEXT_INVALID", path)
        raw = text.encode("utf-8")
        _require(hashlib.sha256(raw).hexdigest() == _sha(item["span_sha256"], path), "SPAN_SHA_MISMATCH", path)
        _require(len(raw) == end - start, "SOURCE_SPAN_LENGTH_MISMATCH", path)
        if sid in self.payloads:
            _require(self.payloads[sid][start:end] == raw, "SOURCE_SPAN_BYTES_MISMATCH", path)

    def assignment(self, value: Any) -> dict:
        item = _obj(value, _ASSIGNMENT, "assignment")
        for field in ("example_id", "post_id"):
            _text(item[field], "assignment." + field)
        path = item["example_id"]
        _require(path not in self.examples, "DUPLICATE_EXAMPLE_ID", path)
        self.examples.add(path)
        _enum(item["split"], set(SPLITS), path + ".split")
        _enum(item["truth_kind"], {"CANDIDATE", "NIL", "UNJUDGED"}, path + ".truth_kind")
        _enum(item["binding_status"], {"UNIQUE", "MISSING", "AMBIGUOUS", "NOT_APPLICABLE"}, path + ".binding_status")
        _text(item["split_group_id"], path + ".split_group_id", nullable=True)
        self.missing(item["split_group_id"] is None, "SPLIT_GROUP_MISSING", path)
        for field in ("content_fingerprint", "source_group_fingerprint", "label_provenance_sha256", "candidate_set_fingerprint", "gold_work_fingerprint"):
            _sha(item[field], path + "." + field, nullable=True)
            self.missing(item[field] is None and (field != "gold_work_fingerprint" or item["truth_kind"] == "CANDIDATE"), "ASSIGNMENT_SHA_MISSING", path + "." + field)
        matched = _ids(item["matched_candidate_ids"], path + ".matched_candidate_ids", 64)
        _require(matched == sorted(matched), "MATCHED_IDS_NOT_SORTED", path)
        _text(item["truth_label"], path + ".truth_label", nullable=True)
        truth, status = item["truth_kind"], item["binding_status"]
        if truth == "CANDIDATE":
            _require(status in {"UNIQUE", "MISSING", "AMBIGUOUS"}, "CANDIDATE_BINDING_INVALID", path)
            if status == "UNIQUE":
                _require(item["truth_label"] not in {None, "__NIL__"} and matched == [item["truth_label"]], "TRUTH_ID_MISMATCH", path)
            else:
                _require(item["truth_label"] is None and (len(matched) == 0 if status == "MISSING" else len(matched) >= 2), "TRUTH_ID_MISMATCH", path)
                self.issue("MISSING", "CANDIDATE_BINDING_" + status, path)
        elif truth == "NIL":
            _require(item["truth_label"] == "__NIL__" and status == "NOT_APPLICABLE" and not matched and item["gold_work_fingerprint"] is None, "NIL_BINDING_INVALID", path)
        else:
            _require(item["truth_label"] is None and status in {"NOT_APPLICABLE", "MISSING", "AMBIGUOUS"}, "UNJUDGED_BINDING_INVALID", path)
            self.issue("MISSING", "TRUTH_UNJUDGED", path)
        for field in ("post_id", "split_group_id", "content_fingerprint", "source_group_fingerprint", "candidate_set_fingerprint", "gold_work_fingerprint"):
            self.leak(field, item[field], item)
        return item

    def row(self, value: Any):
        row = _obj(value, {"assignment", "binding", "source_ids", "source_spans", "exposures", "r2_id_bridges", "role_mentions", "label_provenance"}, "row")
        assignment = self.assignment(row["assignment"])
        path, split = assignment["example_id"], assignment["split"]
        counts = self.counts[split]
        counts["rows"] += 1
        counts["unjudged_rows"] += assignment["truth_kind"] == "UNJUDGED"
        self.posts[split].add(assignment["post_id"])
        binding = _obj(row["binding"], {"run_id", "attempt_id", "input_index"}, path + ".binding")
        for field in ("run_id", "attempt_id"):
            _text(binding[field], path + "." + field, nullable=True)
            self.missing(binding[field] is None, "RUN_BINDING_MISSING", path + "." + field)
        _require(type(binding["input_index"]) is int and binding["input_index"] > 0, "INPUT_INDEX_INVALID", path)
        if binding["run_id"] is not None and binding["attempt_id"] is not None:
            coordinate = (binding["run_id"], binding["attempt_id"], binding["input_index"])
            _require(coordinate not in self.coordinates, "DUPLICATE_RUN_COORDINATE", path)
            self.coordinates.add(coordinate)
        source_ids = _ids(row["source_ids"], path + ".source_ids")
        self.missing(not source_ids, "ROW_SOURCES_MISSING", path)
        for sid in source_ids:
            _require(sid in self.sources, "SOURCE_NOT_FOUND", path + "." + sid)
            source = self.sources[sid]
            for field in ("source_id", "payload_sha256", "source_group_id", "lineage_root_id"):
                self.leak(field, source[field], assignment)
        groups = [self.sources[sid]["source_group_id"] for sid in source_ids]
        if source_ids and all(group is not None for group in groups):
            if assignment["source_group_fingerprint"] is not None:
                _require(assignment["source_group_fingerprint"] == canonical_sha256(sorted(set(groups))), "SOURCE_GROUP_SHA_MISMATCH", path)
        else:
            _require(assignment["source_group_fingerprint"] is None, "UNKNOWN_SOURCE_GROUP_HASH_INVENTED", path)
        spans = _list(row["source_spans"], path + ".source_spans", 256)
        self.missing(not spans, "QUERY_SOURCE_SPANS_MISSING", path)
        for span in spans:
            self.span(span, source_ids, path)
            self.leak("query_span_content", span["span_sha256"], assignment)
        if assignment["content_fingerprint"] is not None:
            _require(assignment["content_fingerprint"] == canonical_sha256(spans), "CONTENT_SHA_MISMATCH", path)
        provenance = self.provenance(row["label_provenance"], path + ".label_provenance", "WORK_IDENTITY")
        _require(assignment["label_provenance_sha256"] == provenance["artifact_sha256"], "LABEL_PROVENANCE_SHA_MISMATCH", path)
        exposures = _list(row["exposures"], path + ".exposures", 64)
        candidates = {}
        for exposure in exposures:
            _obj(exposure, _EXPOSURE, path + ".exposure")
            cid = _text(exposure["candidate_id"], path + ".candidate_id")
            _require(cid != "__NIL__" and cid not in candidates, "EXPOSURE_ID_INVALID", path)
            candidates[cid] = exposure
            polarity = _enum(exposure["polarity"], {"POSITIVE", "NEGATIVE", "UNJUDGED"}, path + ".polarity")
            counts["candidates"] += 1
            counts[{"POSITIVE": "positive", "NEGATIVE": "negative", "UNJUDGED": "unjudged_exposures"}[polarity]] += 1
            self.missing(polarity == "UNJUDGED", "EXPOSURE_LABEL_UNJUDGED", path + "." + cid)
            for field in ("corpus_candidate_id", "work_id", "edition_id", "media_type"):
                _text(exposure[field], path + "." + field, nullable=True)
                self.missing(exposure[field] is None and field != "corpus_candidate_id", "EXPOSURE_IDENTITY_UNKNOWN", path + "." + cid + "." + field)
            families = exposure["alias_family_ids"]
            if families is None:
                self.issue("MISSING", "ALIAS_FAMILY_UNKNOWN", path + "." + cid)
            else:
                _ids(families, path + ".alias_family_ids", 64)
                for family in families:
                    self.leak("alias_family_id", family, assignment)
            used_sources = _ids(exposure["source_ids"], path + ".exposure.source_ids")
            self.missing(not used_sources, "EXPOSURE_SOURCES_MISSING", path + "." + cid)
            _require(set(used_sources) <= set(source_ids), "EXPOSURE_SOURCE_NOT_BOUND", path)
            previous = self.identity.setdefault(cid, {})
            for field in ("work_id", "edition_id", "media_type"):
                known = exposure[field]
                if known is not None:
                    _require(field not in previous or previous[field] == known, "CANDIDATE_IDENTITY_CONFLICT", path + "." + cid)
                    previous[field] = known
            for field in ("candidate_id", "corpus_candidate_id", "work_id"):
                self.leak(field, exposure[field], assignment)
            if exposure["edition_id"] is not None and exposure["media_type"] is not None:
                self.leak("edition_media", canonical_sha256([exposure["edition_id"], exposure["media_type"]]), assignment)
        _require(set(assignment["matched_candidate_ids"]) <= set(candidates), "TRUTH_CANDIDATE_NOT_EXPOSED", path)
        if assignment["truth_kind"] == "CANDIDATE" and assignment["binding_status"] == "UNIQUE":
            _require(candidates[assignment["truth_label"]]["polarity"] == "POSITIVE", "TRUTH_POLARITY_CONFLICT", path)
        if assignment["truth_kind"] == "NIL":
            _require(not any(item["polarity"] == "POSITIVE" for item in exposures), "NIL_POSITIVE_CONFLICT", path)
        bridges = {}
        for bridge in _list(row["r2_id_bridges"], path + ".r2_id_bridges", 64):
            _obj(bridge, {"corpus_candidate_id", "status", "candidate_ids", "provenance_sha256"}, path + ".bridge")
            corpus_id = _text(bridge["corpus_candidate_id"], path + ".corpus_candidate_id")
            _require(corpus_id not in bridges, "DUPLICATE_R2_BRIDGE", path)
            bridges[corpus_id] = bridge
            status = _enum(bridge["status"], {"UNIQUE", "MISSING", "AMBIGUOUS"}, path + ".bridge.status")
            ids = _ids(bridge["candidate_ids"], path + ".bridge.candidate_ids", 64)
            _require((len(ids) == 1 if status == "UNIQUE" else len(ids) == 0 if status == "MISSING" else len(ids) >= 2), "R2_BRIDGE_CARDINALITY_INVALID", path)
            _require(set(ids) <= set(candidates), "R2_BRIDGE_CANDIDATE_NOT_EXPOSED", path)
            _require(all(candidates[cid]["corpus_candidate_id"] == corpus_id for cid in ids), "R2_BRIDGE_ID_MISMATCH", path)
            self.evidence_ref(bridge["provenance_sha256"], path + ".bridge.provenance_sha256")
            self.missing(status != "UNIQUE", "R2_BRIDGE_" + status, path)
            if status == "UNIQUE":
                self.unique_corpus_binding(corpus_id, candidates[ids[0]], assignment)
        for cid, exposure in candidates.items():
            corpus_id = exposure["corpus_candidate_id"]
            if corpus_id is not None:
                self.missing(corpus_id not in bridges, "R2_BRIDGE_MISSING", path + "." + cid)
                if corpus_id in bridges and bridges[corpus_id]["status"] != "MISSING":
                    _require(cid in bridges[corpus_id]["candidate_ids"], "R2_BRIDGE_ID_MISMATCH", path + "." + cid)
        mentioned, seen_mentions = set(), set()
        for mention in _list(row["role_mentions"], path + ".role_mentions", 128):
            _obj(mention, {"candidate_id", "source_span", "roles", "provenance"}, path + ".role_mention")
            cid = _text(mention["candidate_id"], path + ".role_mention.candidate_id")
            _require(cid in candidates, "ROLE_CANDIDATE_NOT_EXPOSED", path)
            self.span(mention["source_span"], source_ids, path)
            roles = _ids(mention["roles"], path + ".roles", 5)
            _require(bool(roles) and set(roles) <= {"PRIMARY", "PREVIOUS", "MENTIONED", "COMPARISON", "UNKNOWN"} and ("UNKNOWN" not in roles or roles == ["UNKNOWN"]), "ROLE_INVALID", path)
            self.missing(roles == ["UNKNOWN"], "ROLE_UNKNOWN", path + "." + cid)
            marker = canonical_sha256([cid, mention["source_span"]])
            _require(marker not in seen_mentions, "DUPLICATE_ROLE_MENTION", path)
            seen_mentions.add(marker)
            mentioned.add(cid)
            self.provenance(mention["provenance"], path + ".role_provenance", "MENTION_ROLE")
        for cid in sorted(set(candidates) - mentioned):
            self.issue("MISSING", "ROLE_MENTION_MISSING", path + "." + cid)


def validate_training_split(manifest: Any, *, source_payloads: Mapping[str, bytes], evidence_payloads: Mapping[str, bytes], calibration_manifest: Any = None, expected_calibration_sha256: Any = None) -> dict:
    """Validate declared split/exposure and supplied bytes; never mutate inputs."""
    validator = _Validator(source_payloads, evidence_payloads)
    manifest_sha = None
    calibration_sha = None
    bridge = "NOT_PROVIDED"
    input_rows = None
    try:
        _require(isinstance(source_payloads, Mapping) and isinstance(evidence_payloads, Mapping), "PAYLOAD_MAP_INVALID", "payloads")
        payload_values = list(source_payloads.values()) + list(evidence_payloads.values())
        _require(all(type(raw) is bytes for raw in payload_values) and sum(len(raw) for raw in payload_values) <= MAX_BYTES, "PAYLOAD_BYTES_LIMIT_OR_TYPE", "payloads")
        _require(len(_bytes(manifest)) <= MAX_BYTES, "MANIFEST_BYTE_LIMIT", "manifest")
        body = _obj(manifest, {"schema_version", "data_kind", "split_policy_version", "sources", "rows", "manifest_sha256"}, "manifest")
        _require(body["schema_version"] == SCHEMA_VERSION and body["split_policy_version"] == POLICY_VERSION, "VERSION_UNSUPPORTED", "manifest")
        validator.kind = _enum(body["data_kind"], {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}, "data_kind")
        manifest_sha = _sha(body["manifest_sha256"], "manifest_sha256")
        _require(seal_manifest(body)["manifest_sha256"] == manifest_sha, "MANIFEST_SHA_MISMATCH", "manifest")
        for source in _list(body["sources"], "sources", MAX_SOURCES):
            try:
                validator.source(source)
            except _Invalid as exc:
                validator.issue("ERROR", exc.code, exc.path)
        rows = _list(body["rows"], "rows", MAX_ROWS)
        input_rows = len(rows)
        for row in rows:
            try:
                validator.row(row)
            except (_Invalid, UnicodeError, TypeError, ValueError) as exc:
                validator.issue("ERROR", getattr(exc, "code", "ROW_ENCODING_INVALID"), getattr(exc, "path", "row"))
        for split, counts in validator.counts.items():
            counts["unique_posts"] = len(validator.posts[split])
            validator.missing(counts["rows"] == 0, "SPLIT_EMPTY", split)
        if calibration_manifest is not None:
            bridge = "INVALID"
            _sha(expected_calibration_sha256, "expected_calibration_sha256")
            # Import the established validator only for an explicitly requested bridge.
            from .candidate_set_calibration_shadow import CalibrationSplitAssignment, CalibrationSplitManifest
            data = deepcopy(dict(calibration_manifest))
            data["assignments"] = tuple(CalibrationSplitAssignment(**item) for item in data["assignments"])
            verified = CalibrationSplitManifest(**data)
            calibration_sha = verified.manifest_sha256
            _require(calibration_sha == expected_calibration_sha256, "CALIBRATION_MANIFEST_SHA_MISMATCH", "calibration_manifest")
            expected = sorted(calibration_assignments(body), key=lambda item: item["example_id"])
            observed = sorted(verified.to_dict()["assignments"], key=lambda item: item["example_id"])
            _require(observed == expected, "CALIBRATION_ASSIGNMENT_MISMATCH", "calibration_manifest")
            bridge = "BOUND"
        elif expected_calibration_sha256 is not None:
            _sha(expected_calibration_sha256, "expected_calibration_sha256")
            validator.issue("MISSING", "CALIBRATION_MANIFEST_MISSING", "calibration_manifest")
    except (_Invalid, TypeError, ValueError, KeyError, UnicodeError, RecursionError) as exc:
        validator.issue("ERROR", getattr(exc, "code", "MANIFEST_OR_BRIDGE_INVALID"), getattr(exc, "path", "manifest"))
    errors = sum(issue["severity"] == "ERROR" for issue in validator.issues)
    missing = sum(issue["severity"] == "MISSING" for issue in validator.issues)
    status = "INVALID" if errors else "NOT_READY" if missing else "VALID"
    report = {"schema_version": "reranker_training_split_validation_v1", "status": status, "data_kind": validator.kind,
              "manifest_sha256": manifest_sha, "calibration_manifest_sha256": calibration_sha, "calibration_bridge_status": bridge,
              "ready_for_calibration_bridge": status == "VALID" and bridge == "BOUND", "issues": validator.issues,
              "counts": {"by_split": validator.counts, "total_rows": input_rows, "parsed_assignment_rows": sum(item["rows"] for item in validator.counts.values()), "unique_posts": len(set().union(*validator.posts.values())), "error_count": errors, "missing_count": missing, "provenance_grade_observations": dict(sorted(validator.grades.items()))},
              "exposure_completeness": "DECLARED_NOT_INDEPENDENTLY_VERIFIED",
              "publication_authority": False, "model_training_executed": False, "actual_performance_evaluated": False}
    report["report_sha256"] = canonical_sha256(report)
    return report
