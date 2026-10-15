"""Frozen, explicitly injected BM25 candidate observations with no public authority.

No runtime, model, network or database imports. Corpus bytes are read once by
load_corpus; observe only uses immutable in-memory data and the caller's original
source fragments. Declared source references are not independent source proofs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
from types import MappingProxyType
from typing import Any, Mapping


CORPUS_SCHEMA = "frozen_candidate_corpus_v1"
SOURCE_VIEW_SCHEMA = "candidate_retrieval_source_view_v1"
RECEIPT_SCHEMA = "candidate_retrieval_shadow_v1"
TOKENIZER_VERSION = "regex_ko_alnum_lower_v1"
SCORER_VERSION = "bm25_k1_b_query_frequency_v1"
QUERY_POLICY_VERSION = "original_fragments_separate_tokens_v1"
MAX_CORPUS_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_RECEIPT_BYTES = 48 * 1024
MAX_QUERY_CHARS = 12000
MAX_QUERY_FRAGMENTS = 128
MAX_QUERY_TOKENS = 2048
MAX_SCORING_OPERATIONS = 2_000_000
TOKEN_RE = re.compile(r"[0-9a-zA-Z가-힣]+")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
BODY_PATH = re.compile(r"/(?:content|content_blocks/(?:0|[1-9][0-9]{0,8})/text)\Z")
COMMENT_PATH = re.compile(r"/comments/(?:0|[1-9][0-9]{0,8})(?:/(?:content|text))?\Z")
MEDIA_TYPES = frozenset({"WEB_NOVEL", "NOVEL", "WEBTOON", "COMIC", "AUDIOBOOK", "GAME", "OTHER"})


class CandidateRetrievalShadowError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


CorpusError = CandidateRetrievalShadowError


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def candidate_content_sha256(title: str, aliases: list[str], text: str) -> str:
    """Hash the exact corpus text view; not a hash of a fetched source page."""
    return _sha({"title": title, "aliases": aliases, "text": text})


def _fail(code: str, field: str) -> None:
    raise CandidateRetrievalShadowError(code, field)


def _object(value: Any, required: set[str], field: str, optional=frozenset()) -> dict:
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        _fail("SCHEMA_INVALID", field)
    return value


def _text(value: Any, field: str, limit: int, *, empty=False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        _fail("FIELD_INVALID", field)
    try:
        value.encode("utf-8")
    except UnicodeError:
        _fail("FIELD_INVALID", field)
    return value


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        _fail("SHA256_INVALID", field)
    return value


def _date(value: Any, field: str) -> datetime:
    text = _text(value, field, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _fail("TIMESTAMP_INVALID", field)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("TIMESTAMP_INVALID", field)
    return parsed


def _config(top_k: int, k1: float, b: float) -> dict:
    if type(top_k) is not int or not 1 <= top_k <= 100:
        _fail("CONFIG_INVALID", "top_k must be integer 1..100")
    if type(k1) not in (int, float) or not math.isfinite(k1) or not 0 < k1 <= 4:
        _fail("CONFIG_INVALID", "k1 must be finite, 0 < k1 <= 4")
    if type(b) not in (int, float) or not math.isfinite(b) or not 0 <= b <= 1:
        _fail("CONFIG_INVALID", "b must be finite, 0 <= b <= 1")
    return {
        "top_k": top_k, "k1": float(k1), "b": float(b),
        "tokenizer_version": TOKENIZER_VERSION, "scorer_version": SCORER_VERSION,
        "query_policy_version": QUERY_POLICY_VERSION, "positive_scores_only": True,
        "max_query_chars": MAX_QUERY_CHARS, "max_query_fragments": MAX_QUERY_FRAGMENTS,
        "max_query_tokens": MAX_QUERY_TOKENS, "max_scoring_operations": MAX_SCORING_OPERATIONS,
        "max_receipt_bytes": MAX_RECEIPT_BYTES,
    }


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("DUPLICATE_JSON_KEY", key)
            result[key] = value
        return result
    def constant(_value):
        _fail("NONFINITE_JSON", "corpus")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CandidateRetrievalShadowError("CORPUS_JSON_INVALID", "corpus is not strict UTF-8 JSON") from exc


@dataclass(frozen=True)
class _Document:
    candidate_id: str
    work_id: str
    edition_id: str
    media_type: str
    title: str
    aliases: tuple[str, ...]
    text: str
    content_sha256: str
    sources_json: bytes
    mirror_candidate_ids: tuple[str, ...]
    token_count: int
    frequencies: Mapping[str, int]


def _parse_entry(value: Any, data_kind: str) -> dict:
    fields = {"corpus_candidate_id", "work_id", "edition_id", "media_type",
              "title", "aliases", "text", "content_sha256", "sources"}
    entry = _object(value, fields, "corpus entry")
    for field in ("corpus_candidate_id", "work_id", "edition_id"):
        _text(entry[field], field, 128)
    if not isinstance(entry["media_type"], str) or entry["media_type"] not in MEDIA_TYPES:
        _fail("MEDIA_TYPE_INVALID", "media_type")
    _text(entry["title"], "title", 512)
    _text(entry["text"], "text", 20000, empty=True)
    aliases = entry["aliases"]
    if not isinstance(aliases, list) or len(aliases) > 32:
        _fail("ALIASES_INVALID", "aliases")
    for alias in aliases:
        _text(alias, "alias", 512)
    if len(set(aliases)) != len(aliases):
        _fail("DUPLICATE_ALIAS", "aliases")
    expected_content = _hash(entry["content_sha256"], "content_sha256")
    if candidate_content_sha256(entry["title"], aliases, entry["text"]) != expected_content:
        _fail("CONTENT_SHA256_MISMATCH", "candidate content")
    sources = entry["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
        _fail("PROVENANCE_LIMIT_OR_MISSING", "sources")
    seen_refs = set()
    for source in sources:
        _object(source, {"source_ref", "source_sha256", "lineage_id", "observed_at", "rights"}, "source")
        source_ref = _text(source["source_ref"], "source_ref", 2048)
        _hash(source["source_sha256"], "source_sha256")
        _text(source["lineage_id"], "lineage_id", 256)
        _date(source["observed_at"], "observed_at")
        rights = _object(source["rights"], {"status", "basis"}, "rights")
        expected_rights = "SYNTHETIC_FIXTURE" if data_kind == "SYNTHETIC_FIXTURE" else "REUSE_PERMITTED"
        if rights["status"] != expected_rights:
            _fail("RIGHTS_NOT_DECLARED", "rights.status")
        _text(rights["basis"], "rights.basis", 512)
        if source_ref in seen_refs:
            _fail("DUPLICATE_SOURCE_REF", "sources")
        seen_refs.add(source_ref)
    return entry


def _query(source_view: Any) -> tuple[Any, str, tuple[str, ...], list[dict]]:
    view = _object(source_view, {"schema_version", "post_id", "fragments"}, "source_view")
    if view["schema_version"] != SOURCE_VIEW_SCHEMA:
        _fail("SOURCE_VIEW_SCHEMA_INVALID", "source_view")
    post_id = view["post_id"]
    if not ((type(post_id) is int and 0 <= post_id <= 2**63 - 1) or
            (isinstance(post_id, str) and post_id.strip() and len(post_id) <= 128)):
        _fail("POST_ID_INVALID", "post_id")
    fragments = view["fragments"]
    if not isinstance(fragments, list):
        _fail("SOURCE_VIEW_INVALID", "fragments")
    if len(fragments) > MAX_QUERY_FRAGMENTS:
        _fail("QUERY_FRAGMENT_LIMIT", "fragments")
    total_chars, query_tokens, summaries, seen_paths = 0, [], [], set()
    for fragment in fragments:
        _object(fragment, {"raw_path", "kind", "text"}, "fragment")
        path = _text(fragment["raw_path"], "raw_path", 96)
        kind = fragment["kind"]
        if not ((kind == "TITLE" and path == "/title") or
                (kind == "BODY" and BODY_PATH.fullmatch(path)) or
                (kind == "COMMENT" and COMMENT_PATH.fullmatch(path))):
            _fail("SOURCE_PATH_KIND_INVALID", "fragment")
        if path in seen_paths:
            _fail("DUPLICATE_SOURCE_PATH", "fragment")
        seen_paths.add(path)
        text = fragment["text"]
        if not isinstance(text, str):
            _fail("SOURCE_TEXT_INVALID", "fragment")
        total_chars += len(text)
        if total_chars > MAX_QUERY_CHARS:
            _fail("QUERY_CHAR_LIMIT", "fragments")
        _text(text, "fragment text", MAX_QUERY_CHARS, empty=True)
        query_tokens.extend(_tokens(text))
        if len(query_tokens) > MAX_QUERY_TOKENS:
            _fail("QUERY_TOKEN_LIMIT", "fragments")
        summaries.append({"raw_path": path, "kind": kind, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                          "char_count": len(text)})
    return post_id, _sha(view), tuple(query_tokens), summaries


def _receipt(policy: dict, *, status: str, reason_codes: list[str],
             post_id=None, query_sha256=None, source_fragments=None, ranked_candidates=None,
             token_count=0, positive_count=0, started=None) -> dict:
    value = {
        "schema_version": RECEIPT_SCHEMA, "mode": "SHADOW", "status": status,
        "reason_codes": reason_codes, "publication_authority": False,
        "public_apply": False, "central_db_write": False,
        "post_id": post_id, "corpus_sha256": policy.get("corpus_sha256"),
        "scorer_sha256": policy["scorer_sha256"], "config_sha256": policy["config_sha256"],
        "query_sha256": query_sha256, "source_fragments": source_fragments or [],
        "ranked_candidates": ranked_candidates or [], "policy": policy,
        "counts": {"query_tokens": token_count, "positive_candidates": positive_count,
                   "returned_candidates": len(ranked_candidates or []), "omitted_ranked_candidates": 0},
        "latency_ms": round((time.perf_counter() - started) * 1000, 3) if started is not None else 0.0,
    }
    initial_count = len(value["ranked_candidates"])
    # Drop only a tail of complete candidates. Never detach provenance from a hit.
    while len(_bytes(value)) > MAX_RECEIPT_BYTES and value["ranked_candidates"]:
        value["ranked_candidates"].pop()
        value["status"] = "RECEIPT_LIMIT_EXCEEDED"
        value["reason_codes"] = list(dict.fromkeys([*reason_codes, "RECEIPT_BYTE_LIMIT"]))
        value["counts"]["returned_candidates"] = len(value["ranked_candidates"])
        value["counts"]["omitted_ranked_candidates"] = initial_count - len(value["ranked_candidates"])
    if len(_bytes(value)) > MAX_RECEIPT_BYTES:
        # Source fragments have a separate fixed cap; this is defensive fallback.
        value["source_fragments"] = []
        value["status"] = "RECEIPT_LIMIT_EXCEEDED"
        value["reason_codes"] = ["RECEIPT_BYTE_LIMIT_SOURCE_DETAILS_OMITTED"]
    value["observation_sha256"] = _sha({key: item for key, item in value.items() if key != "latency_ms"})
    # Reserve the final digest size too.
    if len(_bytes(value)) > MAX_RECEIPT_BYTES:
        value["source_fragments"] = []
        value["ranked_candidates"] = []
        value["status"] = "RECEIPT_LIMIT_EXCEEDED"
        value["reason_codes"] = ["RECEIPT_BYTE_LIMIT_FINAL_DIGEST"]
        value["counts"]["returned_candidates"] = 0
        value["counts"]["omitted_ranked_candidates"] = initial_count
        value["observation_sha256"] = _sha({key: item for key, item in value.items() if key not in {"latency_ms", "observation_sha256"}})
    return value


@dataclass(frozen=True)
class FrozenCandidateRetrievalShadow:
    _policy_json: bytes
    _documents: tuple[_Document, ...]
    _postings: Mapping[str, tuple[tuple[int, int], ...]]
    _average_length: float
    _top_k: int
    _k1: float
    _b: float

    @property
    def policy(self) -> dict:
        return json.loads(self._policy_json)

    def summary(self) -> dict:
        return self.policy

    def observe(self, source_view: Mapping[str, Any]) -> dict:
        started = time.perf_counter()
        policy = self.policy
        try:
            post_id, query_sha, tokens, fragments = _query(source_view)
        except CandidateRetrievalShadowError as exc:
            status = "QUERY_LIMIT_EXCEEDED" if exc.code.startswith("QUERY_") else "INVALID_SOURCE_VIEW"
            observed_post = source_view.get("post_id") if isinstance(source_view, dict) else None
            if not ((type(observed_post) is int and 0 <= observed_post <= 2**63 - 1) or
                    (isinstance(observed_post, str) and observed_post.strip() and len(observed_post) <= 128)):
                observed_post = None
            return _receipt(policy, status=status, reason_codes=[exc.code], post_id=observed_post, started=started)
        common = {"post_id": post_id, "query_sha256": query_sha, "source_fragments": fragments,
                  "token_count": len(tokens), "started": started}
        if not tokens:
            return _receipt(policy, status="EMPTY_QUERY", reason_codes=["NO_QUERY_TOKENS"], **common)
        if not self._documents:
            return _receipt(policy, status="EMPTY_CORPUS", reason_codes=["NO_CORPUS_DOCUMENTS"], **common)
        operations = sum(len(self._postings.get(token, ())) for token in tokens)
        if operations > MAX_SCORING_OPERATIONS:
            return _receipt(policy, status="SCORING_LIMIT_EXCEEDED", reason_codes=["SCORING_OPERATION_LIMIT"], **common)
        scores = defaultdict(float)
        size = len(self._documents)
        for token in tokens:
            postings = self._postings.get(token, ())
            frequency = len(postings)
            inverse = math.log(1.0 + (size - frequency + 0.5) / (frequency + 0.5))
            for index, term_count in postings:
                document = self._documents[index]
                denominator = term_count + self._k1 * (1.0 - self._b + self._b * document.token_count / max(1.0, self._average_length))
                scores[index] += inverse * term_count * (self._k1 + 1.0) / denominator
        ranked = sorted(((index, score) for index, score in scores.items() if score > 0),
                        key=lambda pair: (-pair[1], self._documents[pair[0]].candidate_id))
        hits = []
        for index, score in ranked[:self._top_k]:
            document = self._documents[index]
            hits.append({
                "corpus_candidate_id": document.candidate_id,
                "work_id": document.work_id, "edition_id": document.edition_id,
                "media_type": document.media_type, "title": document.title, "score": score,
                "content_sha256": document.content_sha256,
                "mirror_candidate_ids": list(document.mirror_candidate_ids),
                "source_refs": json.loads(document.sources_json),
                "authority_status": "RETRIEVAL_OBSERVATION_ONLY",
            })
        return _receipt(policy, status="OK" if hits else "NO_MATCH",
                        reason_codes=[] if hits else ["NO_POSITIVE_SCORE"],
                        ranked_candidates=hits, positive_count=len(ranked), **common)


@dataclass(frozen=True)
class UnavailableCandidateRetrievalShadow:
    _policy_json: bytes
    code: str

    @property
    def policy(self) -> dict:
        return json.loads(self._policy_json)

    def summary(self) -> dict:
        return self.policy

    def observe(self, source_view: Mapping[str, Any]) -> dict:
        started = time.perf_counter()
        common = {}
        try:
            post_id, query_sha, tokens, fragments = _query(source_view)
            common = {"post_id": post_id, "query_sha256": query_sha, "token_count": len(tokens), "source_fragments": fragments}
        except CandidateRetrievalShadowError:
            pass
        return _receipt(self.policy, status="UNAVAILABLE_CORPUS", reason_codes=[self.code], started=started, **common)


def _policy(config: dict, corpus_sha256: str | None) -> dict:
    return {
        "schema_version": "candidate_retrieval_policy_v1", "mode": "SHADOW",
        "publication_authority": False, "public_apply": False, "central_db_write": False,
        "corpus_sha256": corpus_sha256, "config": config, "config_sha256": _sha(config),
        "scorer_sha256": _sha({key: config[key] for key in ("k1", "b", "tokenizer_version", "scorer_version", "query_policy_version")}),
        "source_refs_independently_verified": False,
        "provenance_verification": "DECLARED_SOURCE_REFS_CORPUS_BYTES_VERIFIED",
    }


def unavailable_observer(code: str, *, expected_sha256: str | None, top_k=20) -> UnavailableCandidateRetrievalShadow:
    config = _config(top_k, 1.5, .75)
    if expected_sha256 is not None:
        _hash(expected_sha256, "expected_sha256")
    policy = _policy(config, expected_sha256)
    policy.update(status="UNAVAILABLE_CORPUS", reason_codes=[_text(code, "code", 128)],
                  provenance_verification="CORPUS_NOT_VERIFIED")
    return UnavailableCandidateRetrievalShadow(_bytes(policy), code)


def load_corpus(path: str | Path, *, expected_sha256: str, top_k=20,
                k1=1.5, b=.75, as_of: datetime | None = None) -> FrozenCandidateRetrievalShadow:
    """Read and verify one explicit corpus. No source_ref is fetched or opened."""
    config = _config(top_k, k1, b)
    _hash(expected_sha256, "expected_sha256")
    try:
        with Path(path).open("rb") as source:
            raw = source.read(MAX_CORPUS_BYTES + 1)
    except OSError as exc:
        raise CandidateRetrievalShadowError("CORPUS_UNAVAILABLE", "cannot read pinned corpus") from exc
    return load_corpus_bytes(raw, expected_sha256=expected_sha256, top_k=top_k,
                             k1=k1, b=b, as_of=as_of)


def load_corpus_bytes(raw: bytes, *, expected_sha256: str, top_k=20,
                      k1=1.5, b=.75, as_of: datetime | None = None) -> FrozenCandidateRetrievalShadow:
    """Verify an explicit in-memory corpus using the identical file-loader contract."""
    config = _config(top_k, k1, b)
    _hash(expected_sha256, "expected_sha256")
    if type(raw) is not bytes:
        _fail("CORPUS_BYTES_REQUIRED", "corpus")
    if len(raw) > MAX_CORPUS_BYTES:
        _fail("CORPUS_BYTE_LIMIT", "corpus")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha256:
        _fail("CORPUS_SHA256_MISMATCH", "corpus")
    corpus = _object(_strict_json(raw), {"schema_version", "corpus_id", "data_kind", "entries"},
                     "corpus", optional={"valid_until"})
    if corpus["schema_version"] != CORPUS_SCHEMA:
        _fail("CORPUS_SCHEMA_INVALID", "schema_version")
    corpus_id = _text(corpus["corpus_id"], "corpus_id", 128)
    data_kind = corpus["data_kind"]
    if not isinstance(data_kind, str) or data_kind not in {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}:
        _fail("CORPUS_DATA_KIND_INVALID", "data_kind")
    if "valid_until" in corpus:
        expiry = _date(corpus["valid_until"], "valid_until")
        now = as_of or datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            _fail("CONFIG_INVALID", "as_of must be timezone aware")
        if now >= expiry:
            _fail("CORPUS_EXPIRED", "valid_until")
    entries = corpus["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        _fail("CORPUS_ENTRY_LIMIT_OR_INVALID", "entries")
    seen_ids, groups = set(), defaultdict(list)
    for value in entries:
        entry = _parse_entry(value, data_kind)
        candidate_id = entry["corpus_candidate_id"]
        if candidate_id in seen_ids:
            _fail("DUPLICATE_CANDIDATE_ID", "corpus_candidate_id")
        seen_ids.add(candidate_id)
        key = (entry["work_id"], entry["edition_id"], entry["media_type"], entry["content_sha256"],
               tuple(sorted({source["lineage_id"] for source in entry["sources"]})))
        groups[key].append(entry)
    documents = []
    for group in groups.values():
        group.sort(key=lambda entry: entry["corpus_candidate_id"])
        first = group[0]
        source_by_ref = {}
        for entry in group:
            for source in entry["sources"]:
                ref = source["source_ref"]
                if ref in source_by_ref and source_by_ref[ref] != source:
                    _fail("MIRROR_SOURCE_REF_CONFLICT", "sources")
                source_by_ref[ref] = source
        if len(source_by_ref) > 8:
            _fail("MIRROR_PROVENANCE_LIMIT", "sources")
        document_tokens = [token for field in [first["title"], *first["aliases"], first["text"]] for token in _tokens(field)]
        frequencies = MappingProxyType(dict(Counter(document_tokens)))
        documents.append(_Document(
            first["corpus_candidate_id"], first["work_id"], first["edition_id"], first["media_type"],
            first["title"], tuple(first["aliases"]), first["text"], first["content_sha256"],
            _bytes([source_by_ref[key] for key in sorted(source_by_ref)]),
            tuple(entry["corpus_candidate_id"] for entry in group[1:]), len(document_tokens), frequencies,
        ))
    documents.sort(key=lambda document: document.candidate_id)
    postings = defaultdict(list)
    for index, document in enumerate(documents):
        for token, count in document.frequencies.items():
            postings[token].append((index, count))
    policy = _policy(config, actual_sha)
    policy.update(status="READY", corpus_id=corpus_id, data_kind=data_kind,
                  input_entry_count=len(entries), indexed_document_count=len(documents),
                  mirror_deduplicated_count=len(entries) - len(documents),
                  valid_until=corpus.get("valid_until"), freshness_status="EXPLICIT_EXPIRY_CHECKED" if "valid_until" in corpus else "NO_EXPIRY_POLICY_DECLARED")
    return FrozenCandidateRetrievalShadow(
        _bytes(policy), tuple(documents), MappingProxyType({key: tuple(value) for key, value in postings.items()}),
        sum(document.token_count for document in documents) / max(1, len(documents)),
        top_k, float(k1), float(b),
    )


load_candidate_retrieval_shadow = load_corpus


def configure_candidate_retrieval_shadow(*, mode="OFF", corpus_path=None,
                                         expected_sha256=None, top_k=20):
    """OFF has no load. Invalid config fails; invalid corpus yields diagnostics."""
    if mode == "OFF":
        return None
    if mode != "SHADOW" or corpus_path is None or expected_sha256 is None:
        _fail("CONFIG_INVALID", "SHADOW requires explicit corpus path and expected SHA256")
    _config(top_k, 1.5, .75)
    _hash(expected_sha256, "expected_sha256")
    try:
        return load_corpus(corpus_path, expected_sha256=expected_sha256, top_k=top_k)
    except CandidateRetrievalShadowError as exc:
        return unavailable_observer(exc.code, expected_sha256=expected_sha256, top_k=top_k)

