"""검토된 R3 별칭과 고정 R2 후보의 순수 결속 검산. 파일/모델/네트워크 IO 없음.

HUMAN_REVIEW_BOUND는 제공된 review 원문 결속이며 사람의 신원이나 관계의
진실을 독립 인증하지 않는다. 원문 view, 후보 집합, 공개 결정은 변경하지 않는다.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
from typing import Mapping

from . import community_knowledge as ck
from . import candidate_retrieval_shadow as retrieval
from .candidate_reranker_roles import _boundaries, POLICY_SHA256 as TITLE_BOUNDARY_POLICY_SHA256
from .candidate_reranker_shadow import _source, _validate_view, build_frozen_view


INPUT_SCHEMA = "candidate_reranker_alias_evidence_input_v1"
SCHEMA_VERSION = "candidate_reranker_alias_evidence_v1"
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_FILES = 4096
MAX_RECEIPT_BYTES = 48 * 1024
MAX_OCCURRENCES = 128
MAX_RAW_MATCHES = 4096
STATIC_FIELDS = frozenset({"schema_version", "snapshot_manifest_sha256", "snapshot_files", "corpus_sha256"})
CALL_FIELDS = STATIC_FIELDS | {"retrieval_receipt", "community_source_view"}
POLICY = {
    "schema_version": SCHEMA_VERSION, "snapshot_schema": ck.MANIFEST_SCHEMA,
    "review_schema": "community_knowledge_classification_review_v1",
    "relation": "R3_EXPLICIT_DEFINITION_WITH_WHOLE_CANONICAL_TITLE",
    "mapping": "PINNED_CORPUS_WORK_EDITION_MEDIA_UNIQUE_IN_FIXED_CANDIDATES",
    "review_time": "SNAPSHOT_BUILT_AT_NOT_AFTER_AS_OF",
    "matching": "EXACT_RAW_SURFACE_WITH_V1_TITLE_PARTICLE_BOUNDARIES",
    "literal_boundary_policy_sha256": TITLE_BOUNDARY_POLICY_SHA256,
    "competing_senses": "UNBOUND", "unknown_lineage": "UNBOUND",
    "max_input_bytes": MAX_INPUT_BYTES, "max_receipt_bytes": MAX_RECEIPT_BYTES,
    "max_occurrences": MAX_OCCURRENCES, "max_raw_matches": MAX_RAW_MATCHES,
    "public_apply": False, "publication_authority": False, "central_db_write": False,
}


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_sha256(value):
    return _sha(_bytes(value))


POLICY_SHA256 = canonical_sha256(POLICY)


class AliasEvidenceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise AliasEvidenceError(code)


def _hash(value):
    _require(type(value) is str and retrieval.SHA_RE.fullmatch(value) is not None, "SHA256_INVALID")
    return value


def _path(value):
    _require(type(value) is str and 0 < len(value) <= 512, "SNAPSHOT_PATH_INVALID")
    parts = PurePosixPath(value)
    _require(not parts.is_absolute() and not any(part in {"", ".", ".."} for part in value.split("/"))
             and "\\" not in value and ":" not in value and "\x00" not in value, "SNAPSHOT_PATH_INVALID")
    return value


class _MemoryFiles:
    """R3 검산자의 read 계약만 구현한다. 경로 접근이나 사용자 callback 없음."""
    def __init__(self, paths, payloads, manifest_size):
        self.paths, self.payloads = paths, payloads
        self.total, self.seen = manifest_size, set()

    def read(self, relative, expected, maximum=ck.MAX_SNAPSHOT_BYTES):
        name, digest = _path(relative), _hash(expected)
        _require(self.paths.get(name) == digest, "SNAPSHOT_FILE_BINDING_MISMATCH")
        raw = self.payloads.get(digest)
        _require(type(raw) is bytes, "EVIDENCE_PAYLOAD_MISSING")
        _require(len(raw) <= maximum, "SNAPSHOT_LIMIT_EXCEEDED")
        if name not in self.seen:
            self.total += len(raw)
            self.seen.add(name)
        _require(self.total <= ck.MAX_SNAPSHOT_BYTES, "SNAPSHOT_LIMIT_EXCEEDED")
        return raw


def _snapshot(raw, files):
    """기존 R3의 행·원문·분류 검산을 그대로 사용하고 로더 orchestration만 순수화."""
    manifest = ck._obj(ck._strict_json(raw), {"schema_version", "snapshot_id", "data_kind", "built_at", "freeze_cutoff",
        "parser_version", "normalization_version", "query_policy_version", "rights_policy_version", "lineage_policy_version", "files"}, "manifest")
    versions = {"schema_version": ck.MANIFEST_SCHEMA, "parser_version": ck.CORE_VERSION,
        "normalization_version": "utf8_identity_v1", "query_policy_version": ck.QUERY_POLICY_VERSION,
        "rights_policy_version": "local_asserted_reuse_v1", "lineage_policy_version": "declared_root_no_independent_authority_v1"}
    _require(all(manifest[key] == value for key, value in versions.items()), "SNAPSHOT_VERSION_UNSUPPORTED")
    ck._text(manifest["snapshot_id"], "snapshot_id", 128)
    kind = ck._enum(manifest["data_kind"], {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}, "data_kind")
    built = ck._date(manifest["built_at"], "built_at")
    _require(ck._date(manifest["freeze_cutoff"], "freeze_cutoff") <= built, "TIME_ORDER_INVALID")
    specs = ck._obj(manifest["files"], {"candidate_ledger", "work_alias_registry", "community_lexicon", "source_inventory"}, "files")
    loaded, count = {}, 0
    for name, spec in specs.items():
        count_key = "source_count" if name == "source_inventory" else "rows"
        ck._obj(spec, {"path", "sha256", count_key}, name)
        _require(type(spec[count_key]) is int and 0 <= spec[count_key] <= ck.MAX_ROWS, "SNAPSHOT_LIMIT_EXCEEDED")
        data = files.read(spec["path"], spec["sha256"])
        if name == "source_inventory":
            obj = ck._obj(ck._strict_json(data), {"schema_version", "sources"}, name)
            _require(obj["schema_version"] == "community_knowledge_source_inventory_v1", "SOURCE_INVENTORY_SCHEMA_INVALID")
            rows = obj["sources"]
            _require(type(rows) is list and len(rows) <= ck.MAX_SOURCES, "SOURCE_LIMIT_EXCEEDED")
        else:
            lines = data.splitlines()
            _require(all(line.strip() for line in lines), "JSONL_BLANK_ROW")
            count += len(lines)
            _require(count <= ck.MAX_ROWS, "SNAPSHOT_LIMIT_EXCEEDED")
            rows = [ck._strict_json(line) for line in lines]
        _require(len(rows) == spec[count_key], "ROW_COUNT_MISMATCH")
        loaded[name] = rows
    sources, observed, full_observations = {}, {}, {}
    for item in loaded["source_inventory"]:
        source, observations = ck._source(item, files, kind, built)
        sid = source["source_id"]
        _require(sid not in sources, "DUPLICATE_SOURCE_ID")
        sources[sid], observed[sid] = source, observations
        parsed = ck.parse_capture(source_profile=source["capture_profile"], content_type="text/plain; charset=utf-8",
            capture_version=source["capture_version"], normalization_version=source["normalization_version"],
            payload=files.read(source["payload_ref"], source["payload_byte_sha256"], ck.MAX_PAYLOAD_BYTES))
        full_observations[sid] = parsed["observations"]
    for sid, source in sources.items():
        seen, current = {sid}, source
        while current["parent_id"] in sources:
            parent = sources[current["parent_id"]]
            _require(parent["source_id"] not in seen, "LINEAGE_CYCLE")
            seen.add(parent["source_id"])
            if current["lineage_status"] == parent["lineage_status"] == "DECLARED":
                _require(current["lineage_root_id"] == parent["lineage_root_id"], "LINEAGE_ROOT_CONFLICT")
            current = parent
    candidates, senses = {}, {}
    for item in loaded["candidate_ledger"]:
        row = ck._candidate(item, sources, observed, files, kind)
        cid, sense = row["candidate_id"], row["sense_candidate_id"]
        _require(cid not in candidates, "DUPLICATE_CANDIDATE_ID")
        identity = canonical_sha256({key: row[key] for key in ("surface_raw", "definition_text", "community_scope", "temporal_scope")})
        _require(sense not in senses or senses[sense] == identity, "SENSE_ID_CONFLICT")
        candidates[cid], senses[sense] = row, identity
    aliases = ck._classifications(loaded["work_alias_registry"], candidates, files, kind, "work_alias_registry")
    lexicon = ck._classifications(loaded["community_lexicon"], candidates, files, kind, "community_lexicon")
    reviews = {}
    for group in aliases.values():
        for entry in group:
            reference = entry["review"]
            if reference["receipt_sha256"] is not None:
                raw_review = files.read(reference["receipt_ref"], reference["receipt_sha256"], 256 * 1024)
                reviews[reference["receipt_sha256"]] = ck._strict_json(raw_review)
    return {"manifest": manifest, "sources": sources, "candidates": candidates, "aliases": aliases,
            "lexicon": lexicon, "observations": full_observations, "reviews": reviews}


def _corpus(raw):
    corpus = retrieval._object(retrieval._strict_json(raw), {"schema_version", "corpus_id", "data_kind", "entries"},
                               "corpus", optional={"valid_until"})
    _require(corpus["schema_version"] == retrieval.CORPUS_SCHEMA, "CORPUS_SCHEMA_INVALID")
    retrieval._text(corpus["corpus_id"], "corpus_id", 128)
    _require(corpus["data_kind"] in {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}, "CORPUS_DATA_KIND_INVALID")
    if "valid_until" in corpus:
        retrieval._date(corpus["valid_until"], "valid_until")
    entries = corpus["entries"]
    _require(type(entries) is list and len(entries) <= retrieval.MAX_ENTRIES, "CORPUS_ENTRY_LIMIT_OR_INVALID")
    seen, groups = set(), defaultdict(list)
    for value in entries:
        entry = retrieval._parse_entry(value, corpus["data_kind"])
        _require(entry["corpus_candidate_id"] not in seen, "DUPLICATE_CORPUS_ID")
        seen.add(entry["corpus_candidate_id"])
        key = (entry["work_id"], entry["edition_id"], entry["media_type"], entry["content_sha256"],
               tuple(sorted({source["lineage_id"] for source in entry["sources"]})))
        groups[key].append(entry)
    rows = {}
    for group in groups.values():
        group.sort(key=lambda entry: entry["corpus_candidate_id"])
        first, sources = group[0], {}
        for entry in group:
            for source in entry["sources"]:
                ref = source["source_ref"]
                _require(ref not in sources or sources[ref] == source, "MIRROR_SOURCE_REF_CONFLICT")
                sources[ref] = source
        _require(len(sources) <= 8, "MIRROR_PROVENANCE_LIMIT")
        rows[first["corpus_candidate_id"]] = {key: first[key] for key in
            ("corpus_candidate_id", "work_id", "edition_id", "media_type", "title", "content_sha256")}
        rows[first["corpus_candidate_id"]].update(mirror_candidate_ids=[item["corpus_candidate_id"] for item in group[1:]],
                                                source_refs=[sources[key] for key in sorted(sources)])
    return {"data_kind": corpus["data_kind"], "valid_until": corpus.get("valid_until"), "rows": rows}


def _prepare_alias_evidence(*, alias_evidence, evidence_payloads):
    """정적 R3/R2 bytes를 한 번 검산한다. 원문 assertion의 진실은 인증하지 않는다."""
    _require(type(alias_evidence) is dict and set(alias_evidence) == STATIC_FIELDS, "ALIAS_STATIC_SCHEMA_INVALID")
    _require(alias_evidence["schema_version"] == INPUT_SCHEMA, "ALIAS_INPUT_SCHEMA_INVALID")
    _require(isinstance(evidence_payloads, Mapping) and len(evidence_payloads) <= MAX_FILES, "EVIDENCE_FILES_INVALID")
    paths = alias_evidence["snapshot_files"]
    _require(type(paths) is dict and len(paths) <= MAX_FILES, "SNAPSHOT_FILES_INVALID")
    for name, digest in paths.items():
        _path(name)
        _hash(digest)
    total = len(_bytes(alias_evidence))
    payloads = {}
    for digest, raw in evidence_payloads.items():
        _hash(digest)
        _require(type(raw) is bytes, "EVIDENCE_PAYLOAD_TYPE_INVALID")
        total += len(raw)
        _require(total <= MAX_INPUT_BYTES, "ALIAS_INPUT_BYTE_LIMIT")
        _require(_sha(raw) == digest, "EVIDENCE_PAYLOAD_SHA_MISMATCH")
        payloads[digest] = raw
    manifest_sha, corpus_sha = (_hash(alias_evidence[key]) for key in ("snapshot_manifest_sha256", "corpus_sha256"))
    _require(all(digest in payloads for digest in [manifest_sha, corpus_sha, *paths.values()]), "EVIDENCE_PAYLOAD_MISSING")
    _require(len(payloads[manifest_sha]) <= ck.MAX_SNAPSHOT_BYTES, "SNAPSHOT_LIMIT_EXCEEDED")
    memory = _MemoryFiles(dict(paths), payloads, len(payloads[manifest_sha]))
    bundle, corpus = _snapshot(payloads[manifest_sha], memory), _corpus(payloads[corpus_sha])
    _require(bundle["manifest"]["data_kind"] == corpus["data_kind"], "DATA_KIND_MISMATCH")
    return FrozenAliasEvidence(_bytes({"snapshot": bundle, "corpus": corpus}), _bytes(alias_evidence))


def prepare_alias_evidence(*, alias_evidence, evidence_payloads):
    """기존 검산자의 오류도 하나의 명시 오류 타입으로 전달한다."""
    try:
        return _prepare_alias_evidence(alias_evidence=alias_evidence, evidence_payloads=evidence_payloads)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError) as exc:
        if isinstance(exc, AliasEvidenceError):
            raise
        raise AliasEvidenceError(getattr(exc, "code", "ALIAS_EVIDENCE_INVALID")) from exc


def build_alias_community_source_view(source_view, *, community, as_of):
    """R2 원문을 복사한다. 문맥 객체는 호출자가 명시 원문에서 공급해야 한다."""
    _require(type(source_view) is dict, "SOURCE_VIEW_INVALID")
    _source(source_view, source_view.get("post_id"))
    value = {"schema_version": ck.SOURCE_VIEW_SCHEMA, "post_id": source_view["post_id"],
             "fragments": source_view["fragments"], "community": community, "as_of": as_of}
    ck._source_view(value)
    for key in ("community", "as_of"):
        _require(value[key]["status"] != "UNKNOWN" or value[key]["value"] is None, "UNKNOWN_CONTEXT_VALUE_NOT_NULL")
        _require(value[key]["source_path"] == ("/gallery_id" if key == "community" else "/created_at"), "CONTEXT_SOURCE_PATH_INVALID")
    return json.loads(_bytes(value))


def _seal(value):
    value["receipt_sha256"] = canonical_sha256(value)
    if len(_bytes(value)) > MAX_RECEIPT_BYTES:
        value.pop("receipt_sha256")
        value.update(status="LIMIT_EXCEEDED", reason_codes=["ALIAS_RECEIPT_BYTE_LIMIT"], bindings=[], unresolved=[])
        value["counts"]["bindings"] = 0
        value["receipt_sha256"] = canonical_sha256(value)
    return value


def _base():
    return {"schema_version": SCHEMA_VERSION, "status": "NO_MATCH", "reason_codes": [], "policy_sha256": POLICY_SHA256,
        "post_id": None, "frozen_view_sha256": None, "source_sha256": None, "snapshot_sha256": None, "corpus_sha256": None,
        "query_sha256": None, "alias_evidence_sha256": None, "data_kind": None,
        "bindings": [], "unresolved": [], "counts": {"surfaces": 0, "occurrences": 0, "bindings": 0, "unresolved": 0},
        "publication_authority": False, "public_authority": False, "public_apply": False, "central_db_write": False,
        "actual_semantic_evidence_verified": False, "reviewer_identity_verified": False,
        "rights_authority_independently_verified": False}


def _review_binding(bundle, row, alias):
    reference = alias["review"]
    _require(row.get("review") == reference, "REVIEW_REGISTRY_BINDING_MISMATCH")
    review = bundle["reviews"].get(reference["receipt_sha256"])
    _require(type(review) is dict and set(review) == {"schema_version", "source_id", "payload_byte_sha256", "observation_sha256",
        "review_status", "authority", "reviewer", "sense_candidate_id", "classification"}, "REVIEW_SCHEMA_INVALID")
    ref = alias["explicit_alias_assertion_ref"]
    source = bundle["sources"][ref["source_id"]]
    observation = next((item for item in bundle["observations"][source["source_id"]]
        if all(item[key] == ref[key] for key in ("utf8_byte_span_start", "utf8_byte_span_end", "evidence_text", "evidence_utf8_sha256"))
        and item["surface_text"] == row["surface_raw"] and item["presented_definition_text"] == row["definition_text"]), None)
    _require(observation is not None, "REVIEW_OBSERVATION_MISSING")
    expected = {"schema_version": "community_knowledge_classification_review_v1", "source_id": source["source_id"],
        "payload_byte_sha256": source["payload_byte_sha256"], "observation_sha256": observation["observation_sha256"],
        "review_status": row["review_status"], "authority": reference["authority"], "reviewer": reference["reviewer"],
        "sense_candidate_id": row["sense_candidate_id"], "classification": {"namespace": "work_alias_registry",
        **{key: alias[key] for key in ("work_id", "edition_id", "media_type", "canonical_title", "canonical_title_locator")}}}
    _require(review == expected, "REVIEW_SOURCE_CLASSIFICATION_BINDING_MISMATCH")
    return source, observation


def _relation(row, alias, observation):
    _require(row["definition_text"] == alias["canonical_title"], "CANONICAL_TITLE_MISMATCH")
    text, surface, title = observation["evidence_text"], row["surface_raw"], alias["canonical_title"]
    # The parser has already checked one of its four complete neutral grammars.
    prefix = "'" + surface + "'"
    _require(text.startswith(prefix) and text[len(prefix):len(prefix) + 2] in {"은 ", "는 "}
             and text.endswith(("을 뜻한다.", "를 뜻한다.")), "RELATION_NOT_EXPLICIT")
    title_start = len(prefix) + 2
    _require(text[title_start:title_start + len(title)] == title, "RELATION_TITLE_SPAN_MISMATCH")
    base = observation["utf8_byte_span_start"]
    def span(start, end):
        return [base + len(text[:start].encode("utf-8")), base + len(text[:end].encode("utf-8"))]
    predicate_start = len(text) - len("뜻한다.")
    return {"raw_utf8_span": [base, observation["utf8_byte_span_end"]], "text_sha256": observation["evidence_utf8_sha256"],
        "alias_utf8_span": span(1, 1 + len(surface)), "title_utf8_span": span(title_start, title_start + len(title)),
        "predicate_utf8_span": span(predicate_start, predicate_start + len("뜻한다")), "predicate": "뜻한다"}


def _occurrences(view, surfaces):
    _require(len(surfaces) * len(view["fragments"]) <= ck.MAX_COMPARISONS, "ALIAS_COMPARISON_LIMIT")
    result, raw_matches, count = {}, 0, 0
    for surface in sorted(surfaces):
        for fragment in view["fragments"]:
            text, offset = fragment["text"], 0
            while True:
                start = text.find(surface, offset)
                if start < 0:
                    break
                end, offset = start + len(surface), start + 1
                raw_matches += 1
                _require(raw_matches <= MAX_RAW_MATCHES, "ALIAS_RAW_MATCH_LIMIT")
                if not _boundaries(text, start, end):
                    continue
                count += 1
                _require(count <= MAX_OCCURRENCES, "ALIAS_OCCURRENCE_LIMIT")
                result.setdefault(surface, []).append({"raw_path": fragment["raw_path"], "kind": fragment["kind"],
                    "start": start, "end": end, "text_sha256": _sha(text[start:end].encode("utf-8")),
                    "utf8_byte_span_start": len(text[:start].encode("utf-8")), "utf8_byte_span_end": len(text[:end].encode("utf-8"))})
    return result


@dataclass(frozen=True)
class FrozenAliasEvidence:
    _bundle_json: bytes
    _static_json: bytes

    def summary(self):
        bundle, static = json.loads(self._bundle_json), json.loads(self._static_json)
        return {"schema_version": SCHEMA_VERSION, "status": "AVAILABLE", "policy_sha256": POLICY_SHA256,
            "snapshot_sha256": static["snapshot_manifest_sha256"], "corpus_sha256": static["corpus_sha256"],
            "alias_evidence_sha256": canonical_sha256(static), "data_kind": bundle["snapshot"]["manifest"]["data_kind"],
            "actual_semantic_evidence_verified": False, "publication_authority": False}

    def observe(self, frozen_view, *, retrieval_receipt, community_source_view):
        value = _base()
        value.update({key: item for key, item in self.summary().items() if key in value and key != "status"})
        try:
            return self._observe(value, frozen_view, retrieval_receipt, community_source_view)
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError) as exc:
            code = getattr(exc, "code", "ALIAS_EVIDENCE_INVALID")
            value.update(status="LIMIT_EXCEEDED" if "LIMIT" in code else "INVALID_INPUT", reason_codes=[code], bindings=[], unresolved=[])
            value["counts"]["bindings"] = value["counts"]["unresolved"] = 0
            return _seal(value)

    def _observe(self, value, frozen_view, receipt, query):
        view = _validate_view(frozen_view)
        _require(view == build_frozen_view(view["source_view"], receipt), "FROZEN_RETRIEVAL_VIEW_MISMATCH")
        value.update(post_id=view["post_id"], frozen_view_sha256=canonical_sha256(view), source_sha256=canonical_sha256(view["source_view"]))
        _require(type(query) is dict, "COMMUNITY_SOURCE_VIEW_INVALID")
        ck._source_view(query)
        exact_query = build_alias_community_source_view(view["source_view"], community=query["community"], as_of=query["as_of"])
        _require(_bytes(exact_query) == _bytes(query), "COMMUNITY_SOURCE_VIEW_MISMATCH")
        value["query_sha256"] = canonical_sha256(query)
        bundle = json.loads(self._bundle_json)
        snapshot, corpus = bundle["snapshot"], bundle["corpus"]
        _require(type(receipt.get("policy")) is dict, "RETRIEVAL_POLICY_INVALID")
        _require(receipt.get("corpus_sha256") == value["corpus_sha256"] and receipt.get("policy", {}).get("corpus_sha256") == value["corpus_sha256"], "RETRIEVAL_CORPUS_SHA_MISMATCH")
        _require(receipt.get("policy", {}).get("data_kind") == value["data_kind"], "RETRIEVAL_DATA_KIND_MISMATCH")
        fixed = {}
        for row in receipt["ranked_candidates"]:
            expected = corpus["rows"].get(row["corpus_candidate_id"])
            _require(expected is not None and all(row.get(key) == item for key, item in expected.items()), "RETRIEVAL_CORPUS_IDENTITY_MISMATCH")
            fixed[row["corpus_candidate_id"]] = expected
        if view["generation_status"] != "COMPLETE":
            value.update(status="UNRESOLVED", reason_codes=["GENERATION_NOT_COMPLETE"])
            return _seal(value)
        if any(query[key]["status"] != "EXPLICIT" for key in ("community", "as_of")):
            value.update(status="UNRESOLVED", reason_codes=["CONTEXT_UNKNOWN"])
            return _seal(value)
        as_of = ck._date(query["as_of"]["value"], "as_of")
        if ck._date(snapshot["manifest"]["built_at"], "built_at") > as_of:
            value.update(status="UNRESOLVED", reason_codes=["SNAPSHOT_AFTER_AS_OF"])
            return _seal(value)
        if corpus["valid_until"] is not None and as_of >= retrieval._date(corpus["valid_until"], "valid_until"):
            value.update(status="UNRESOLVED", reason_codes=["CORPUS_EXPIRED"])
            return _seal(value)
        if any(retrieval._date(source["observed_at"], "observed_at") > as_of for candidate in fixed.values() for source in candidate["source_refs"]):
            value.update(status="UNRESOLVED", reason_codes=["CORPUS_SOURCE_NOT_YET_OBSERVED"])
            return _seal(value)
        cutoff = ck._date(snapshot["manifest"]["freeze_cutoff"], "freeze_cutoff")
        occurrences = _occurrences(query, {row["surface_raw"] for row in snapshot["candidates"].values()})
        value["counts"].update(surfaces=len(occurrences), occurrences=sum(map(len, occurrences.values())))
        # Conflicting literal spans are not resolved by title length or source order.
        overlaps = set()
        flattened = [(surface, occurrence) for surface, items in occurrences.items() for occurrence in items]
        for i, (surface, left) in enumerate(flattened):
            for other, right in flattened[i + 1:]:
                if surface != other and left["raw_path"] == right["raw_path"] and max(left["start"], right["start"]) < min(left["end"], right["end"]):
                    overlaps.update((surface, other))
        for surface, hits in occurrences.items():
            reasons, eligible, senses = set(), [], set()
            for row in snapshot["candidates"].values():
                if row["surface_raw"] != surface:
                    continue
                row_eligible = []
                for ref in row["source_refs"]:
                    source = snapshot["sources"][ref["source_id"]]
                    reason = ck._eligibility(row, source, query["community"]["value"], as_of, cutoff)
                    if reason is None:
                        row_eligible.append(ref)
                    else:
                        reasons.add(reason)
                if row_eligible:
                    senses.add(row["sense_candidate_id"])
                    eligible.append((row, row_eligible))
            if len(senses) > 1:
                reasons.add("COMPETING_SENSES")
            declared_identities = {(alias["work_id"], alias["edition_id"], alias["media_type"])
                for row, _ in eligible for alias in snapshot["aliases"].get(row["candidate_id"], [])}
            if len(declared_identities) > 1:
                reasons.add("COMPETING_SENSES")
            if surface in overlaps:
                reasons.add("OVERLAPPING_ALIAS_OCCURRENCES")
            uncertain = {"SOURCE_COMMUNITY_UNKNOWN", "SOURCE_TIME_UNKNOWN", "SENSE_TIME_UNKNOWN", "RIGHTS_NOT_ELIGIBLE"}
            candidates = []
            if not ({"COMPETING_SENSES", "OVERLAPPING_ALIAS_OCCURRENCES"} & reasons or uncertain & reasons):
                for row, refs in eligible:
                    aliases = snapshot["aliases"].get(row["candidate_id"], [])
                    if not aliases:
                        reasons.add("NO_WORK_ALIAS_CLASSIFICATION")
                    if snapshot["lexicon"].get(row["candidate_id"]):
                        reasons.add("COMPETING_SENSES")
                        continue
                    for alias in aliases:
                        try:
                            _require(alias["explicit_alias_assertion_ref"] in refs, "ALIAS_SOURCE_NOT_ELIGIBLE")
                            _require(row["review_status"] == "REVIEWED", "ALIAS_NOT_REVIEWED")
                            authority = alias["review"]["authority"]
                            expected_authority = "SYNTHETIC_FIXTURE" if value["data_kind"] == "SYNTHETIC_FIXTURE" else "HUMAN_REVIEW"
                            _require(authority == expected_authority, "REVIEW_AUTHORITY_INSUFFICIENT")
                            _require(type(alias["review"]["reviewer"]) is str and bool(alias["review"]["reviewer"].strip()), "REVIEWER_UNDECLARED")
                            source, observation = _review_binding(snapshot, row, alias)
                            _require(source["lineage_status"] == "DECLARED" and source["lineage_root_id"], "LINEAGE_UNKNOWN")
                            relation = _relation(row, alias, observation)
                            _require(alias["edition_id"] is not None, "EDITION_UNKNOWN")
                            identity = (alias["work_id"], alias["edition_id"], alias["media_type"])
                            matched = [candidate for candidate in fixed.values() if tuple(candidate[key] for key in ("work_id", "edition_id", "media_type")) == identity]
                            _require(len(matched) == 1, "ID_MAPPING_AMBIGUOUS" if matched else "ID_MAPPING_MISSING")
                            candidate = matched[0]
                            _require(candidate["title"] == alias["canonical_title"], "CORPUS_CANONICAL_TITLE_MISMATCH")
                            candidates.append({"candidate_id": candidate["corpus_candidate_id"], "alias": surface, "binding_status": "UNIQUE",
                                "evidence_grade": "SYNTHETIC_FIXTURE_BOUND" if value["data_kind"] == "SYNTHETIC_FIXTURE" else "HUMAN_REVIEW_BOUND",
                                **{key: alias[key] for key in ("work_id", "edition_id", "media_type", "canonical_title", "registry_entry_id")},
                                "registry_row_sha256": alias["row_content_sha256"], "candidate_row_sha256": row["row_content_sha256"],
                                "sense_id": row["sense_candidate_id"], "review_authority": authority,
                                "review_receipt_sha256": alias["review"]["receipt_sha256"], "source_id": source["source_id"],
                                "payload_sha256": source["payload_byte_sha256"], "observation_sha256": observation["observation_sha256"],
                                "lineage_root_id": source["lineage_root_id"], "relation": relation, "occurrences": hits})
                        except AliasEvidenceError as exc:
                            reasons.add(exc.code)
            ids = {item["candidate_id"] for item in candidates}
            if len(ids) > 1 or "COMPETING_SENSES" in reasons:
                reasons.add("COMPETING_SENSES")
                candidates = []
            if candidates:
                # 동일 계보/동일 후보 반복은 독립 근거 수 증가로 주장하지 않는다.
                chosen = min(candidates, key=lambda item: (item["registry_entry_id"], item["registry_row_sha256"]))
                value["bindings"].append(chosen)
            else:
                value["unresolved"].append({"alias": surface, "occurrences": hits, "reason_codes": sorted(reasons or {"NO_ELIGIBLE_ALIAS"})})
        value["counts"].update(bindings=len(value["bindings"]), unresolved=len(value["unresolved"]))
        value["reason_codes"] = sorted({code for item in value["unresolved"] for code in item["reason_codes"]})
        if value["bindings"]:
            value["status"] = "PARTIAL" if value["unresolved"] else "BOUND"
        elif value["unresolved"]:
            value["status"] = "AMBIGUOUS" if {"COMPETING_SENSES", "OVERLAPPING_ALIAS_OCCURRENCES", "ID_MAPPING_AMBIGUOUS"} & set(value["reason_codes"]) else "UNRESOLVED"
        return _seal(value)


def observe_alias_evidence(frozen_view, *, alias_evidence, evidence_payloads):
    """공통 producer facade. 모든 실패는 빈 bindings와 명시 terminal로 반환한다."""
    try:
        _require(type(alias_evidence) is dict and set(alias_evidence) == CALL_FIELDS, "ALIAS_CALL_SCHEMA_INVALID")
        static = {key: alias_evidence[key] for key in STATIC_FIELDS}
        frozen = prepare_alias_evidence(alias_evidence=static, evidence_payloads=evidence_payloads)
        return frozen.observe(frozen_view, retrieval_receipt=alias_evidence["retrieval_receipt"],
                              community_source_view=alias_evidence["community_source_view"])
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError) as exc:
        value = _base()
        code = getattr(exc, "code", "ALIAS_EVIDENCE_INVALID")
        value.update(status="LIMIT_EXCEEDED" if "LIMIT" in code else "INVALID_INPUT", reason_codes=[code])
        return _seal(value)
