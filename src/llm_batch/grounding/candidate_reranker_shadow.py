"""Frozen-candidate SHADOW adapter for fixed fixtures and learned linear models.

No model downloads, network, database or dynamic code loading, and no publication writes.
The optional CandidateOption namespace reuses its fixed existing schema only.
Scores are observations, never probabilities or decisions. Manifest is read once.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any


MANIFEST_SCHEMA = "candidate_reranker_manifest_v1"
VIEW_SCHEMA = "candidate_reranker_frozen_view_v1"
SOURCE_SCHEMA = "candidate_retrieval_source_view_v1"
RECEIPT_SCHEMA = "candidate_reranker_shadow_v1"
FEATURE_SCHEMA = "candidate_reranker_features_v1"
SYNTHETIC_BACKEND = "SYNTHETIC_FIXED_SCORES_V1"
LEARNED_BACKEND = "PAIRWISE_LINEAR_V1"
LEARNED_MANIFEST_SCHEMA = "candidate_reranker_manifest_v2"
NIL_LEARNED_BACKEND = "NIL_AUGMENTED_LINEAR_V1"
NIL_MANIFEST_SCHEMA = "candidate_reranker_manifest_v3"
ALLOWED_BACKENDS = frozenset({SYNTHETIC_BACKEND, LEARNED_BACKEND, NIL_LEARNED_BACKEND})
PROBABILITY_STATUS = "NOT_AVAILABLE_UNCALIBRATED"
DIGEST_SCOPE = "CANONICAL_EXCLUDING_LATENCY_SELF_AND_STORAGE_BINDING"
MAX_MANIFEST_BYTES = 256 * 1024
MAX_INPUT_BYTES = 96 * 1024
MAX_RECEIPT_BYTES = 48 * 1024
MAX_CANDIDATES = 20
MAX_SOURCE_CHARS = 12000
MAX_FRAGMENTS = 128
MAX_ROLES = 128
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BODY_PATH = re.compile(r"/(?:content|content_blocks/(?:0|[1-9][0-9]{0,8})/text)\Z")
_COMMENT_PATH = re.compile(r"/comments/(?:0|[1-9][0-9]{0,8})(?:/(?:content|text))?\Z")
_ROLES = frozenset({"PRIMARY", "PREVIOUS", "MENTIONED", "COMPARISON", "UNKNOWN"})
_VIEW_FIELDS = frozenset({"schema_version", "stage", "post_id", "source_view",
    "candidate_namespace", "generation_sha256", "candidate_set_fingerprint",
    "generation_status", "candidates"})
_CANDIDATE_FIELDS = frozenset({"candidate_id", "titles", "urls", "aliases",
    "option_kind", "event_eligible", "identity_conflict", "negative_evidence",
    "role_observations"})
_ROLE_FIELDS = frozenset({"role", "raw_path", "start", "end", "text_sha256"})
_CONFIG = {
    "adapter_version": "candidate_reranker_shadow_adapter_v1",
    "max_manifest_bytes": MAX_MANIFEST_BYTES, "max_input_bytes": MAX_INPUT_BYTES,
    "max_receipt_bytes": MAX_RECEIPT_BYTES, "max_candidates": MAX_CANDIDATES,
    "max_source_chars": MAX_SOURCE_CHARS, "max_fragments": MAX_FRAGMENTS,
    "max_roles_per_candidate": 32, "max_roles_total": MAX_ROLES,
    "max_values_per_candidate_field": 16, "max_candidate_text_chars": 1024,
    "max_manifest_score_rows": 256, "tie_break": "CANDIDATE_ID_ASC",
    "generation_policy": "COMPLETE_ONLY_NO_TRUNCATION",
}
_FEATURE_CONTRACT = {
    "schema_version": FEATURE_SCHEMA, "stage": "PRE_SELECTION",
    "view_fields": sorted(_VIEW_FIELDS), "candidate_fields": sorted(_CANDIDATE_FIELDS),
    "role_fields": sorted(_ROLE_FIELDS), "roles": sorted(_ROLES),
    "source_fields": ["schema_version", "post_id", "fragments"],
    "fragment_fields": ["raw_path", "kind", "text"],
    "roles_are": "SOURCE_OBSERVATIONS_NOT_GOLD",
    "identity_fingerprints_are": "BINDING_METADATA_NOT_SCORE_FEATURES",
}


class CandidateRerankerShadowError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def _fail(code: str, field: str = "") -> None:
    raise CandidateRerankerShadowError(code, field)


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _object(value: Any, fields: frozenset | set, field: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        _fail("FIELD_ALLOWLIST_INVALID", field)
    return value


def _text(value: Any, limit: int, field: str, *, empty=False) -> str:
    if type(value) is not str or (not empty and not value.strip()):
        _fail("TEXT_INVALID", field)
    if len(value) > limit:
        _fail("FIELD_CHAR_LIMIT", field)
    try:
        value.encode("utf-8")
    except UnicodeError:
        _fail("TEXT_ENCODING_INVALID", field)
    return value


def _hash(value: Any, field: str) -> str:
    if type(value) is not str or not _SHA.fullmatch(value):
        _fail("SHA256_INVALID", field)
    return value


def _id(value: Any) -> str:
    text = _text(value, 160, "candidate_id")
    if text == "__NIL__":
        _fail("RESERVED_NIL_ID", "candidate_id")
    return text


def _valid_post(value: Any) -> bool:
    return ((type(value) is int and 0 <= value <= 2**63 - 1) or
            (type(value) is str and bool(value.strip()) and len(value) <= 128
             and not any(0xD800 <= ord(char) <= 0xDFFF for char in value)))


def _number(value: Any) -> float:
    if type(value) not in (float, int):
        _fail("SCORE_INVALID")
    try:
        score = float(value)
    except (OverflowError, ValueError):
        _fail("SCORE_NONFINITE")
    if not math.isfinite(score):
        _fail("SCORE_NONFINITE")
    return score


def _preflight(value: Any) -> None:
    """Reject oversized/cyclic/non-JSON inputs before copying or scoring."""
    pending = [(value, 0)]
    nodes = 0
    chars = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > 15000 or depth > 12:
            _fail("INPUT_STRUCTURE_LIMIT")
        if type(item) is dict:
            if len(item) > 256:
                _fail("INPUT_STRUCTURE_LIMIT")
            for key, child in item.items():
                if type(key) is not str:
                    _fail("NON_JSON_INPUT")
                chars += len(key)
                pending.append((child, depth + 1))
        elif type(item) is list:
            if len(item) > 256:
                _fail("INPUT_STRUCTURE_LIMIT")
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            chars += len(item)
        elif item is not None and type(item) not in (int, float, bool):
            _fail("NON_JSON_INPUT")
        if chars > MAX_INPUT_BYTES:
            _fail("INPUT_BYTE_LIMIT")


def _source(value: Any, post_id: Any) -> tuple[dict, dict[str, str]]:
    view = _object(value, {"schema_version", "post_id", "fragments"}, "source_view")
    if view["schema_version"] != SOURCE_SCHEMA or type(view["post_id"]) is not type(post_id) or view["post_id"] != post_id:
        _fail("SOURCE_BINDING_INVALID")
    fragments = view["fragments"]
    if type(fragments) is not list:
        _fail("FRAGMENTS_INVALID")
    if len(fragments) > MAX_FRAGMENTS:
        _fail("SOURCE_FRAGMENT_LIMIT")
    texts: dict[str, str] = {}
    chars = 0
    for item in fragments:
        _object(item, {"raw_path", "kind", "text"}, "fragment")
        path = _text(item["raw_path"], 96, "raw_path")
        kind = item["kind"]
        if not ((kind == "TITLE" and path == "/title") or
                (kind == "BODY" and _BODY_PATH.fullmatch(path)) or
                (kind == "COMMENT" and _COMMENT_PATH.fullmatch(path))):
            _fail("SOURCE_PATH_KIND_INVALID")
        if path in texts:
            _fail("DUPLICATE_SOURCE_PATH")
        text = _text(item["text"], MAX_SOURCE_CHARS, "source_text", empty=True)
        chars += len(text)
        if chars > MAX_SOURCE_CHARS:
            _fail("SOURCE_CHAR_LIMIT")
        texts[path] = text
    return view, texts


def _validate_view(value: Any) -> dict:
    _preflight(value)
    view = _object(value, _VIEW_FIELDS, "frozen_candidate_view")
    if view["schema_version"] != VIEW_SCHEMA or view["stage"] != "PRE_SELECTION":
        _fail("VIEW_STAGE_OR_SCHEMA_INVALID")
    if not _valid_post(view["post_id"]):
        _fail("POST_ID_INVALID")
    namespace = view["candidate_namespace"]
    if namespace not in ("CORPUS_CANDIDATE", "CANDIDATE_OPTION"):
        _fail("NAMESPACE_INVALID")
    _hash(view["generation_sha256"], "generation_sha256")
    if namespace == "CORPUS_CANDIDATE":
        if view["candidate_set_fingerprint"] is not None:
            _fail("UNDECLARED_CANDIDATE_OPTION_BRIDGE")
    else:
        _hash(view["candidate_set_fingerprint"], "candidate_set_fingerprint")
    if view["generation_status"] not in ("COMPLETE", "TRUNCATED", "UNKNOWN"):
        _fail("GENERATION_STATUS_INVALID")
    _, texts = _source(view["source_view"], view["post_id"])
    candidates = view["candidates"]
    if type(candidates) is not list:
        _fail("CANDIDATES_INVALID")
    if len(candidates) > MAX_CANDIDATES:
        _fail("CANDIDATE_COUNT_LIMIT")
    seen = set()
    role_count = 0
    for candidate in candidates:
        _object(candidate, _CANDIDATE_FIELDS, "candidate")
        candidate_id = _id(candidate["candidate_id"])
        if candidate_id in seen:
            _fail("DUPLICATE_CANDIDATE_ID")
        seen.add(candidate_id)
        if namespace == "CANDIDATE_OPTION" and not re.fullmatch(r"cand_[0-9a-f]{64}", candidate_id):
            _fail("CANDIDATE_OPTION_ID_INVALID")
        for field in ("titles", "urls", "aliases", "negative_evidence"):
            values = candidate[field]
            if type(values) is not list:
                _fail("CANDIDATE_FIELD_INVALID", field)
            if len(values) > 16:
                _fail("CANDIDATE_FIELD_COUNT_LIMIT", field)
            for text in values:
                _text(text, 1024, field)
        if not candidate["titles"] and not candidate["urls"]:
            _fail("CANDIDATE_IDENTITY_MISSING")
        if candidate["option_kind"] not in ("WORK_CANDIDATE", "UNLINKED_SURFACE", "OBSERVED_LATE_SURFACE"):
            _fail("OPTION_KIND_INVALID")
        if type(candidate["event_eligible"]) is not bool or type(candidate["identity_conflict"]) is not bool:
            _fail("CANDIDATE_FLAGS_INVALID")
        if candidate["event_eligible"] and (candidate["identity_conflict"] or candidate["option_kind"] != "WORK_CANDIDATE"):
            _fail("CANDIDATE_ELIGIBILITY_INVALID")
        if namespace == "CANDIDATE_OPTION":
            # Reuse the exact existing canonical title/URL identity contract.
            # This validates a supplied ID; it never invents a work or ID bridge.
            from .candidate_set_shadow import CandidateOption
            try:
                CandidateOption(candidate_id=candidate_id, titles=tuple(candidate["titles"]),
                    urls=tuple(candidate["urls"]), aliases=tuple(candidate["aliases"]),
                    option_kind=candidate["option_kind"], event_eligible=candidate["event_eligible"],
                    identity_conflict=candidate["identity_conflict"],
                    negative_evidence=tuple(candidate["negative_evidence"]))
            except (ValueError, TypeError):
                _fail("CANDIDATE_OPTION_IDENTITY_INVALID")
        roles = candidate["role_observations"]
        if type(roles) is not list:
            _fail("ROLE_OBSERVATIONS_INVALID")
        role_count += len(roles)
        if len(roles) > 32 or role_count > MAX_ROLES:
            _fail("ROLE_OBSERVATION_LIMIT")
        for role in roles:
            _object(role, _ROLE_FIELDS, "role_observation")
            if role["role"] not in _ROLES:
                _fail("ROLE_INVALID")
            path = _text(role["raw_path"], 96, "role raw_path")
            if path not in texts:
                _fail("ROLE_SOURCE_MISSING")
            start, end = role["start"], role["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(texts[path]):
                _fail("ROLE_SPAN_INVALID")
            if _hash(role["text_sha256"], "role text_sha256") != hashlib.sha256(texts[path][start:end].encode("utf-8")).hexdigest():
                _fail("ROLE_SPAN_SHA_MISMATCH")
    raw = _bytes(view)
    if len(raw) > MAX_INPUT_BYTES:
        _fail("INPUT_BYTE_LIMIT")
    return json.loads(raw)


def _strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(_):
        _fail("SCORE_NONFINITE")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CandidateRerankerShadowError("MANIFEST_JSON_INVALID") from exc


def build_frozen_view(source_view: Any, retrieval_receipt: Any) -> dict:
    """Bind verified R2 observations to original input before expert selection.

    This bridge preserves corpus IDs; it never invents CandidateOption IDs.
    Only successful R2 observations (including NO_MATCH) can become a view.
    Caller preserves other upstream terminal states as an unavailable receipt.
    """
    _preflight(source_view)
    if type(source_view) is not dict or not _valid_post(source_view.get("post_id")):
        _fail("SOURCE_BINDING_INVALID")
    _source(source_view, source_view["post_id"])
    _preflight(retrieval_receipt)
    if type(retrieval_receipt) is not dict:
        _fail("RETRIEVAL_RECEIPT_INVALID")
    raw = _bytes(retrieval_receipt)
    if len(raw) > MAX_RECEIPT_BYTES:
        _fail("RETRIEVAL_RECEIPT_BYTE_LIMIT")
    receipt = json.loads(raw)
    if (receipt.get("schema_version") != "candidate_retrieval_shadow_v1" or
            receipt.get("mode") != "SHADOW" or
            any(receipt.get(flag) is not False for flag in ("publication_authority", "public_apply", "central_db_write")) or
            type(receipt.get("post_id")) is not type(source_view["post_id"]) or
            receipt.get("post_id") != source_view["post_id"]):
        _fail("RETRIEVAL_RECEIPT_BINDING_INVALID")
    if receipt.get("query_sha256") != canonical_sha256(source_view):
        _fail("RETRIEVAL_QUERY_SHA_MISMATCH")
    status = receipt.get("status")
    if type(status) is not str:
        _fail("RETRIEVAL_STATUS_INVALID")
    if status not in ("OK", "NO_MATCH"):
        known = {"EMPTY_QUERY", "EMPTY_CORPUS", "QUERY_LIMIT_EXCEEDED", "INVALID_SOURCE_VIEW",
                 "RECEIPT_LIMIT_EXCEEDED", "SCORING_LIMIT_EXCEEDED", "UNAVAILABLE_CORPUS", "ERROR"}
        _fail("RETRIEVAL_" + status if status in known else "RETRIEVAL_STATUS_INVALID")
    digest = _hash(receipt.get("observation_sha256"), "observation_sha256")
    if digest != canonical_sha256({key: item for key, item in receipt.items()
                                 if key not in {"latency_ms", "observation_sha256", "binding"}}):
        _fail("RETRIEVAL_RECEIPT_SHA_MISMATCH")
    rows = receipt.get("ranked_candidates")
    counts = receipt.get("counts")
    if type(rows) is not list or type(counts) is not dict:
        _fail("RETRIEVAL_COUNTS_INVALID")
    positive = counts.get("positive_candidates")
    returned = counts.get("returned_candidates")
    omitted = counts.get("omitted_ranked_candidates")
    if (any(type(value) is not int or value < 0 for value in (positive, returned, omitted)) or
            returned != len(rows) or positive < returned + omitted):
        _fail("RETRIEVAL_COUNTS_INVALID")
    if (status == "NO_MATCH" and (rows or positive or omitted)) or (status == "OK" and not rows):
        _fail("RETRIEVAL_STATUS_COUNTS_MISMATCH")
    if len(rows) > MAX_CANDIDATES:
        _fail("CANDIDATE_COUNT_LIMIT")
    candidates = []
    for row in rows:
        if type(row) is not dict:
            _fail("RETRIEVAL_CANDIDATE_INVALID")
        candidate_id = _id(row.get("corpus_candidate_id"))
        _text(row.get("title"), 1024, "retrieval title")
        if _number(row.get("score")) <= 0:
            _fail("RETRIEVAL_POSITIVE_SCORE_REQUIRED")
        _hash(row.get("content_sha256"), "retrieval content_sha256")
        candidates.append({"candidate_id": candidate_id, "titles": [row["title"]], "urls": [],
            "aliases": [], "option_kind": "WORK_CANDIDATE", "event_eligible": True,
            "identity_conflict": False, "negative_evidence": [], "role_observations": []})
    view = {"schema_version": VIEW_SCHEMA, "stage": "PRE_SELECTION",
        "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": digest,
        "post_id": source_view["post_id"], "source_view": source_view,
        "candidate_set_fingerprint": None,
        "generation_status": "COMPLETE" if positive == returned and omitted == 0 else "TRUNCATED",
        "candidates": candidates}
    return _validate_view(view)


build_frozen_candidate_view = build_frozen_view


def _summary(manifest_sha: str | None, *, scorer_id=None, available=False, reason=None,
             learned_model=None) -> dict:
    policy = dict(_CONFIG)
    feature_sha = canonical_sha256(_FEATURE_CONTRACT)
    learned = learned_model is not None
    backend = learned_model["backend"] if learned else SYNTHETIC_BACKEND if available else None
    nil_learned = backend == NIL_LEARNED_BACKEND
    if learned:
        feature_sha = canonical_sha256({"frozen_view_contract": _FEATURE_CONTRACT,
                                        "learned_feature_contract": learned_model["feature_contract"]})
    scorer_sha = canonical_sha256({"backend": backend,
        "model_manifest_sha256": manifest_sha, "feature_schema_sha256": feature_sha,
        "adapter_version": _CONFIG["adapter_version"]})
    result = {
        "schema_version": "candidate_reranker_summary_v1", "mode": "SHADOW",
        "status": "AVAILABLE_LEARNED" if learned else "AVAILABLE_SYNTHETIC" if available else "UNAVAILABLE",
        "model_manifest_sha256": manifest_sha, "manifest_sha256": manifest_sha, "scorer_sha256": scorer_sha,
        "feature_schema_sha256": feature_sha, "config_sha256": canonical_sha256(policy),
        "backend": backend, "scorer_id": scorer_id,
        "data_kind": learned_model["data_kind"] if learned else "SYNTHETIC_FIXTURE" if available else "UNAVAILABLE",
        "actual_model_available": learned,
        "training_status": "TRAINED_PAIRWISE_PLUS_NIL_HEAD" if nil_learned else "TRAINED_PAIRWISE_LINEAR" if learned else "NOT_TRAINED_SYNTHETIC_FIXTURE" if available else "NOT_AVAILABLE",
        "reason_codes": [] if available else [reason or "MODEL_NOT_CONFIGURED"],
        "publication_authority": False, "public_apply": False, "central_db_write": False,
        "probability_status": PROBABILITY_STATUS, "policy": policy,
    }
    if learned:
        result.update(model_sha256=canonical_sha256(learned_model),
                      training_split_manifest_sha256=learned_model["training_binding"]["split_manifest_sha256"],
                      model_quality_status="NOT_EVALUATED_BY_ADAPTER",
                      model_kind="LEARNED_LINEAR_WITH_NIL_HEAD" if nil_learned else "LEARNED_LINEAR_BASELINE")
    if nil_learned:
        result.update(nil_head_available=True,
                      candidate_ranker_model_sha256=canonical_sha256(learned_model["base_model"]))
    if learned and learned_model["schema_version"].endswith("_v2"):
        from .candidate_reranker_semantic_input import FEATURE_CONTRACT_SHA256
        from .candidate_reranker_semantics import POLICY_SHA256
        result.update(semantic_input_required=True, semantic_contract_sha256=FEATURE_CONTRACT_SHA256,
                      semantic_policy_sha256=POLICY_SHA256, feature_schema=learned_model["feature_schema"])
    return result


def _run_backend(scores: tuple[tuple[str, float], ...], candidates: list[dict]) -> list[dict]:
    table = dict(scores)
    if any(candidate["candidate_id"] not in table for candidate in candidates):
        _fail("SYNTHETIC_SCORE_MISSING")
    return [{"candidate_id": candidate["candidate_id"], "score": table[candidate["candidate_id"]]}
            for candidate in candidates]


def _validated_scores(rows: Any, candidates: list[dict]) -> list[dict]:
    if type(rows) is not list or len(rows) != len(candidates):
        _fail("BACKEND_ID_SET_MISMATCH")
    expected = {candidate["candidate_id"] for candidate in candidates}
    seen = set()
    result = []
    for row in rows:
        _object(row, {"candidate_id", "score"}, "backend score")
        candidate_id = _id(row["candidate_id"])
        if candidate_id not in expected or candidate_id in seen:
            _fail("BACKEND_ID_SET_MISMATCH")
        seen.add(candidate_id)
        result.append({"candidate_id": candidate_id, "score": _number(row["score"])})
    if seen != expected:
        _fail("BACKEND_ID_SET_MISMATCH")
    return sorted(result, key=lambda item: (-item["score"], item["candidate_id"]))


def _receipt(summary: dict, *, status: str, reasons: list[str], started: float,
             view: dict | None = None, post_id=None, ranked=None, nil_score=None,
             semantic_input=None, backend_invoked=False) -> dict:
    value = {key: summary[key] for key in ("mode", "model_manifest_sha256", "manifest_sha256", "scorer_sha256",
        "feature_schema_sha256", "config_sha256", "backend", "data_kind", "actual_model_available",
        "training_status", "publication_authority", "public_apply", "central_db_write", "probability_status")}
    for key in ("model_sha256", "model_quality_status", "model_kind", "training_split_manifest_sha256",
                "nil_head_available", "candidate_ranker_model_sha256"):
        if key in summary:
            value[key] = summary[key]
    value.update(schema_version=RECEIPT_SCHEMA, status=status, reason_codes=list(reasons),
        post_id=post_id, query_sha256=None, input_sha256=None, candidate_view_sha256=None,
        candidate_namespace=None, candidate_option_bridge_status="MISSING", generation_sha256=None,
        candidate_set_fingerprint=None, generation_status=None, frozen_candidate_ids=[],
        ranked_candidates=ranked or [], candidate_observations=[],
        operational_effect="NONE_SHADOW_ONLY", nil_probability=None, selected_candidate_id=None,
        role_authority="SOURCE_OBSERVATIONS_NOT_GOLD", source_refs_independently_verified=False,
        receipt_digest_scope=DIGEST_SCOPE)
    if view is not None:
        value.update(post_id=view["post_id"], query_sha256=canonical_sha256(view["source_view"]),
            input_sha256=canonical_sha256(view), candidate_view_sha256=canonical_sha256(view["candidates"]),
            candidate_namespace=view["candidate_namespace"],
            candidate_option_bridge_status="MISSING" if view["candidate_namespace"] == "CORPUS_CANDIDATE" else "NOT_REQUIRED",
            generation_sha256=view["generation_sha256"], candidate_set_fingerprint=view["candidate_set_fingerprint"],
            generation_status=view["generation_status"],
            frozen_candidate_ids=[candidate["candidate_id"] for candidate in view["candidates"]],
            candidate_observations=[{"candidate_id": candidate["candidate_id"],
                "role_observations": candidate["role_observations"]} for candidate in view["candidates"]])
    if summary["backend"] == NIL_LEARNED_BACKEND:
        value.update(nil_score=nil_score, event_logits=[])
        if nil_score is not None and view is not None:
            scores = {item["candidate_id"]: item["score"] for item in value["ranked_candidates"]}
            value["event_logits"] = [{"label": item["candidate_id"], "score": scores[item["candidate_id"]]}
                                     for item in view["candidates"]] + [{"label": "__NIL__", "score": nil_score}]
    if summary.get("semantic_input_required") is True:
        value.update({key: summary[key] for key in
            ("semantic_input_required", "semantic_contract_sha256", "semantic_policy_sha256", "feature_schema")})
        valid = semantic_input is not None
        value["semantic_input_sha256"] = semantic_input["input_sha256"] if valid else None
        value["semantic_consumption"] = {
            "schema_version": "candidate_reranker_semantic_consumption_v1",
            "status": "SCORED" if status == "SCORED_LEARNED" else "BACKEND_FAILED" if backend_invoked
                else "INPUT_BOUND_NOT_SCORED" if valid else "NOT_CONSUMED",
            "reason_codes": list(reasons), "input_validated": valid, "backend_invoked": backend_invoked,
            "score_produced": status == "SCORED_LEARNED",
            "semantic_input_sha256": semantic_input["input_sha256"] if valid else None,
            "semantic_contract_sha256": summary["semantic_contract_sha256"],
            "semantic_observation_sha256": canonical_sha256(semantic_input["observation"]) if valid else None,
            "semantic_policy_sha256": summary["semantic_policy_sha256"],
            "scorer_input_sha256": canonical_sha256(view) if valid else None,
        }
    # Reserve room for the digest and clock field; never drop a scored tail.
    if len(_bytes(value)) > MAX_RECEIPT_BYTES - 256:
        value.update(status="LIMIT_EXCEEDED", reason_codes=["RECEIPT_BYTE_LIMIT"],
                     ranked_candidates=[], candidate_observations=[], details_available=False)
        if summary["backend"] == NIL_LEARNED_BACKEND:
            value.update(nil_score=None, event_logits=[])
        if summary.get("semantic_input_required") is True:
            value["semantic_consumption"].update(status="OUTPUT_LIMIT_EXCEEDED", score_produced=False,
                reason_codes=["RECEIPT_BYTE_LIMIT"])
    value["receipt_sha256"] = canonical_sha256(value)
    value["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return value


@dataclass(frozen=True, slots=True)
class FrozenCandidateRerankerShadow:
    _summary_json: bytes
    _scores: tuple[tuple[str, float], ...] = ()
    _model_json: bytes | None = None

    def summary(self) -> dict:
        return json.loads(self._summary_json)

    def score(self, frozen_candidate_view: Any, *, semantic_input=None, evidence_payloads=None) -> dict:
        started = time.perf_counter()
        summary = self.summary()
        post_id = frozen_candidate_view.get("post_id") if type(frozen_candidate_view) is dict else None
        post_id = post_id if _valid_post(post_id) else None
        semantic_required = summary.get("semantic_input_required") is True
        if not semantic_required and (semantic_input is not None or evidence_payloads is not None):
            return _receipt(summary, status="INVALID_INPUT", reasons=["LEGACY_SEMANTIC_INPUT_FORBIDDEN"],
                            started=started, post_id=post_id)
        try:
            view = _validate_view(frozen_candidate_view)
        except CandidateRerankerShadowError as exc:
            return _receipt(summary, status="LIMIT_EXCEEDED" if exc.code.endswith("LIMIT") else "INVALID_INPUT",
                            reasons=[exc.code], started=started, post_id=post_id)
        except Exception:
            return _receipt(summary, status="INVALID_INPUT", reasons=["INPUT_CAPTURE_FAILED"],
                            started=started, post_id=post_id)
        common = {"started": started, "view": view}
        generation = view["generation_status"]
        if generation != "COMPLETE":
            return _receipt(summary, status="NOT_SCORED_GENERATION_" + generation,
                            reasons=["GENERATION_" + generation], **common)
        if not view["candidates"]:
            return _receipt(summary, status="EMPTY_CANDIDATE_SET", reasons=["NO_FROZEN_CANDIDATES"], **common)
        if not any(fragment["text"].strip() for fragment in view["source_view"]["fragments"]):
            return _receipt(summary, status="EMPTY_QUERY", reasons=["NO_SOURCE_TEXT"], **common)
        if summary["status"] not in {"AVAILABLE_SYNTHETIC", "AVAILABLE_LEARNED"}:
            return _receipt(summary, status="UNAVAILABLE_MODEL", reasons=summary["reason_codes"], **common)
        if semantic_required:
            try:
                from .candidate_reranker_semantic_input import validate_semantic_input
                semantic_input = validate_semantic_input(semantic_input,
                    evidence_payloads=evidence_payloads, expected_view=view)
                if semantic_input["contract_sha256"] != summary["semantic_contract_sha256"]:
                    _fail("SEMANTIC_MODEL_CONTRACT_MISMATCH")
            except Exception as exc:
                return _receipt(summary, status="INVALID_INPUT",
                    reasons=[getattr(exc, "code", "SEMANTIC_INPUT_INVALID")], **common)
            common["semantic_input"] = semantic_input
        try:
            # Give the backend a private copy. Neither caller nor receipt inputs
            # become mutable backend state; identity checks run after scoring.
            backend_input = json.loads(_bytes(view["candidates"]))
            nil_score = None
            if summary["backend"] == NIL_LEARNED_BACKEND:
                from .candidate_reranker_nil_learned import score_event_logits
                if semantic_required:
                    common["backend_invoked"] = True
                    event = score_event_logits(json.loads(self._model_json), json.loads(_bytes(view)),
                        semantic_input=semantic_input, evidence_payloads=evidence_payloads)
                else:
                    event = score_event_logits(json.loads(self._model_json), json.loads(_bytes(view)))
                if type(event) is not dict or event.get("nil_probability", "MISSING") is not None:
                    _fail("NIL_EVENT_OUTPUT_INVALID")
                rows = event.get("candidate_scores")
                nil_score = _number(event.get("nil_score"))
                checked = _validated_scores(rows, view["candidates"])
                scores = {row["candidate_id"]: row["score"] for row in checked}
                labels = [row["candidate_id"] for row in view["candidates"]] + ["__NIL__"]
                raw_scores = event.get("raw_scores")
                if (type(raw_scores) is not list or len(raw_scores) != len(labels)
                        or event.get("labels") != labels
                        or [_number(score) for score in raw_scores] != [scores[label] for label in labels[:-1]] + [nil_score]):
                    _fail("NIL_EVENT_ORDER_OR_SCORE_MISMATCH")
            elif self._model_json is not None:
                from .candidate_reranker_learned import score_view
                if semantic_required:
                    common["backend_invoked"] = True
                    rows = score_view(json.loads(self._model_json), json.loads(_bytes(view)),
                        semantic_input=semantic_input, evidence_payloads=evidence_payloads)
                else:
                    rows = score_view(json.loads(self._model_json), json.loads(_bytes(view)))
            else:
                rows = _run_backend(self._scores, backend_input)
            ranked = _validated_scores(rows, view["candidates"])
        except CandidateRerankerShadowError as exc:
            return _receipt(summary, status="ERROR", reasons=[exc.code], **common)
        except Exception:
            return _receipt(summary, status="ERROR", reasons=["BACKEND_EXCEPTION"], **common)
        status = "SCORED_LEARNED" if self._model_json is not None else "SCORED_SYNTHETIC"
        reasons = (["UNCALIBRATED_NIL_HEAD_NO_DECISION"] if summary["backend"] == NIL_LEARNED_BACKEND
                   else ["UNCALIBRATED_LEARNED_LINEAR_BASELINE"] if self._model_json is not None
                   else ["SYNTHETIC_FIXTURE_ONLY_NO_MODEL"])
        return _receipt(summary, status=status, reasons=reasons,
                        ranked=ranked, nil_score=nil_score, **common)


def unavailable_scorer(reason: str = "MODEL_NOT_CONFIGURED", *, expected_sha256: str | None = None) -> FrozenCandidateRerankerShadow:
    reason = _text(reason, 96, "unavailable reason")
    if not re.fullmatch(r"[A-Z0-9_]+", reason):
        _fail("REASON_CODE_INVALID")
    if expected_sha256 is not None:
        _hash(expected_sha256, "expected_sha256")
    return FrozenCandidateRerankerShadow(_bytes(_summary(expected_sha256, reason=reason)))


def load_scorer(model_manifest_path: str | Path, *, expected_sha256: str) -> FrozenCandidateRerankerShadow:
    _hash(expected_sha256, "expected_sha256")
    raw_path = str(model_manifest_path)
    if raw_path.startswith(("\\\\", "//")) or "://" in raw_path:
        _fail("NONLOCAL_MANIFEST_PATH")
    try:
        path = Path(raw_path).resolve(strict=True)
        if str(path).startswith(("\\\\", "//")):
            _fail("NONLOCAL_MANIFEST_PATH")
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetDriveTypeW.restype = wintypes.UINT
            if kernel32.GetDriveTypeW(path.anchor) not in (2, 3, 5, 6):
                _fail("NONLOCAL_MANIFEST_PATH")
        with path.open("rb") as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
    except CandidateRerankerShadowError:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        raise CandidateRerankerShadowError("MANIFEST_UNAVAILABLE") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        _fail("MANIFEST_BYTE_LIMIT")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("MANIFEST_SHA_MISMATCH")
    manifest = _strict_json(raw)
    if type(manifest) is dict and manifest.get("schema_version") in (LEARNED_MANIFEST_SCHEMA, NIL_MANIFEST_SCHEMA):
        _object(manifest, {"schema_version", "scorer_id", "backend", "data_kind", "feature_schema", "model"}, "learned manifest")
        nil_learned = manifest["schema_version"] == NIL_MANIFEST_SCHEMA
        if nil_learned:
            from .candidate_reranker_nil_learned import validate_model
        else:
            from .candidate_reranker_learned import validate_model
        expected_backend = NIL_LEARNED_BACKEND if nil_learned else LEARNED_BACKEND
        if manifest["backend"] != expected_backend:
            _fail("LEARNED_MANIFEST_SCHEMA_INVALID")
        model = validate_model(manifest["model"])
        if manifest["feature_schema"] != model["feature_schema"]:
            _fail("LEARNED_MANIFEST_SCHEMA_INVALID")
        if manifest["data_kind"] != model["data_kind"]:
            _fail("LEARNED_DATA_KIND_MISMATCH")
        scorer_id = _text(manifest["scorer_id"], 128, "scorer_id")
        summary = _summary(expected_sha256, scorer_id=scorer_id, available=True, learned_model=model)
        return FrozenCandidateRerankerShadow(_bytes(summary), _model_json=_bytes(model))
    manifest = _object(manifest, {"schema_version", "scorer_id", "backend", "data_kind", "feature_schema", "scores"}, "manifest")
    if manifest["schema_version"] != MANIFEST_SCHEMA or manifest["feature_schema"] != FEATURE_SCHEMA:
        _fail("MANIFEST_SCHEMA_INVALID")
    if manifest["backend"] != SYNTHETIC_BACKEND:
        _fail("BACKEND_NOT_IMPLEMENTED")
    if manifest["data_kind"] != "SYNTHETIC_FIXTURE":
        _fail("SYNTHETIC_BACKEND_REQUIRES_SYNTHETIC_DATA")
    scorer_id = _text(manifest["scorer_id"], 128, "scorer_id")
    rows = manifest["scores"]
    if type(rows) is not list:
        _fail("MANIFEST_SCORES_INVALID")
    if len(rows) > 256:
        _fail("MANIFEST_SCORE_COUNT_LIMIT")
    seen = set()
    scores = []
    for row in rows:
        _object(row, {"candidate_id", "score"}, "manifest score")
        candidate_id = _id(row["candidate_id"])
        if candidate_id in seen:
            _fail("DUPLICATE_CANDIDATE_ID")
        seen.add(candidate_id)
        scores.append((candidate_id, _number(row["score"])))
    summary = _summary(expected_sha256, scorer_id=scorer_id, available=True)
    return FrozenCandidateRerankerShadow(_bytes(summary), tuple(sorted(scores)))
