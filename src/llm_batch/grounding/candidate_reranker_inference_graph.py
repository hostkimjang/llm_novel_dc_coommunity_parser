"""원시 corpus/source bytes에 결속한 R2 전용 추론 graph. 정답/공개 권한은 없다."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from .candidate_reranker_capture import validate_capture
from .candidate_retrieval_shadow import load_corpus_bytes, MAX_CORPUS_BYTES

SCHEMA = "candidate_reranker_inference_graph_v1"
SCOPE = "BOUNDED_PINNED_R2_CORPUS"
PROOF_SCHEMA = "r2_bounded_inference_proof_v1"
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_PAYLOADS = 4096
MAX_GRAPH_BYTES = 16 * 1024 * 1024


class InferenceGraphError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise InferenceGraphError(code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _copy(value):
    raw = canonical_bytes(value)
    _require(len(raw) <= MAX_GRAPH_BYTES, "GRAPH_BYTE_LIMIT")
    return json.loads(raw)


def _receipt_projection(value):
    # 지연과 저장 binding 이외의 R2 전체 필드를 검산한다.
    return {k: v for k, v in value.items() if k not in {"latency_ms", "binding"}}


def _payloads(value):
    _require(type(value) is dict and len(value) <= MAX_SOURCE_PAYLOADS, "SOURCE_PAYLOAD_MAP_INVALID")
    result, total = {}, 0
    for digest, raw in value.items():
        _require(type(raw) is bytes, "SOURCE_PAYLOAD_BYTES_REQUIRED")
        total += len(raw)
        _require(total <= MAX_SOURCE_BYTES, "SOURCE_PAYLOAD_BYTE_LIMIT")
        _require(type(digest) is str and hashlib.sha256(raw).hexdigest() == digest, "SOURCE_PAYLOAD_SHA_MISMATCH")
        result[digest] = raw
    return result


def build_inference_graph(capture, *, corpus_snapshot: bytes, source_payloads: dict[str, bytes]) -> dict:
    """현재 R2를 실제 재조회한다. scorer/파일/네트워크/label API는 호출하지 않는다.

    COMPLETE는 반환된 고정 R2 범위의 적격 raw NIL 점수를 뜻한다. corpus의
    사실성·권리 주장이나 전체 작품 recall, 새 입력의 정답을 입증하지 않는다.
    """
    _require(type(corpus_snapshot) is bytes, "CORPUS_BYTES_REQUIRED")
    _require(len(corpus_snapshot) <= MAX_CORPUS_BYTES, "CORPUS_BYTE_LIMIT")
    try:
        captured = validate_capture(capture)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise InferenceGraphError("CAPTURE_INVALID") from exc
    payloads = _payloads(source_payloads)
    view, upstream, raw, summary = (captured[k] for k in
        ("frozen_view", "retrieval_receipt", "raw_receipt", "scorer_summary"))
    _require(view["candidate_namespace"] == "CORPUS_CANDIDATE", "CORPUS_CANDIDATE_NAMESPACE_REQUIRED")
    policy = upstream.get("policy")
    _require(type(policy) is dict and type(policy.get("config")) is dict, "R2_POLICY_REQUIRED")
    config = policy["config"]
    corpus_sha = hashlib.sha256(corpus_snapshot).hexdigest()
    _require(corpus_sha == upstream.get("corpus_sha256") == policy.get("corpus_sha256"), "CORPUS_SHA_MISMATCH")
    try:
        observer = load_corpus_bytes(corpus_snapshot, expected_sha256=corpus_sha,
            top_k=config["top_k"], k1=config["k1"], b=config["b"])
        replay = observer.observe(view["source_view"])
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        code = getattr(exc, "code", "R2_REPLAY_INVALID")
        raise InferenceGraphError(code) from exc
    replay_summary = observer.summary()
    _require(canonical_bytes(replay_summary) == canonical_bytes(policy), "R2_POLICY_REPLAY_MISMATCH")
    _require(canonical_bytes(_receipt_projection(upstream)) == canonical_bytes(_receipt_projection(replay)),
             "R2_RECEIPT_REPLAY_MISMATCH")
    _require(replay_summary["data_kind"] == summary.get("data_kind"), "MODEL_CORPUS_DATA_KIND_MISMATCH")
    hits = replay["ranked_candidates"]
    ids = [c["candidate_id"] for c in view["candidates"]]
    _require(ids == [hit["corpus_candidate_id"] for hit in hits], "R2_CAPTURE_CANDIDATE_ORDER_MISMATCH")
    candidates, used = [], {}
    for hit, candidate in zip(hits, view["candidates"]):
        for ref in hit["source_refs"]:
            digest = ref["source_sha256"]
            _require(digest in payloads, "RETRIEVED_SOURCE_BYTES_MISSING")
            used[digest] = payloads[digest]
        candidates.append({"candidate_id": candidate["candidate_id"],
            **{k: hit[k] for k in ("work_id", "edition_id", "media_type", "title", "content_sha256",
                                    "mirror_candidate_ids", "source_refs")},
            "role_observations": candidate["role_observations"], "aliases": candidate["aliases"]})
    counts = replay["counts"]
    generation = view["generation_status"]
    if generation == "COMPLETE":
        _require(counts["positive_candidates"] == counts["returned_candidates"] == len(ids)
                 and counts["omitted_ranked_candidates"] == 0, "R2_COMPLETENESS_COUNTS_MISMATCH")
    if generation != "COMPLETE":
        status, reasons = "TRUNCATED", ["BOUNDED_R2_CANDIDATES_TRUNCATED"]
    elif not ids:
        status, reasons = "EMPTY", ["NO_R2_CANDIDATES_NOT_NIL_TRUTH"]
    elif (raw["status"] != "SCORED_LEARNED" or summary.get("backend") != "NIL_AUGMENTED_LINEAR_V1"
          or summary.get("actual_model_available") is not True):
        status, reasons = "NOT_AVAILABLE", ["LEARNED_NIL_SCORE_NOT_AVAILABLE"]
    else:
        status, reasons = "COMPLETE", []
    labels, scores = [], []
    if status == "COMPLETE":
        events = raw["event_logits"]
        labels, scores = [e["label"] for e in events], [e["score"] for e in events]
        _require(labels == ids + ["__NIL__"], "NIL_EVENT_LABEL_ORDER_MISMATCH")
    proof = {"schema_version": PROOF_SCHEMA, "scope": SCOPE, "status": generation,
        "corpus_sha256": corpus_sha, "query_sha256": upstream["query_sha256"],
        "retrieval_config_sha256": replay_summary["config_sha256"],
        "retrieval_scorer_sha256": replay_summary["scorer_sha256"],
        "retrieval_receipt_sha256": upstream["observation_sha256"],
        "input_entry_count": replay_summary["input_entry_count"],
        "indexed_document_count": replay_summary["indexed_document_count"],
        **{k: counts[k] for k in ("positive_candidates", "returned_candidates", "omitted_ranked_candidates")},
        "source_payload_count": len(used), "source_payload_bytes": sum(map(len, used.values())),
        "candidate_ids_sha256": canonical_sha256(ids), "replay_verified": True,
        "source_bytes_verified": True, "source_claims_independently_verified": False}
    proof["proof_sha256"] = canonical_sha256(proof)
    result = {"schema_version": SCHEMA, "scope": SCOPE, "mode": "SHADOW", "status": status,
        "reason_codes": reasons, "post_id": captured["post_id"], "data_kind": replay_summary["data_kind"],
        "source_view": view["source_view"], "source_view_sha256": canonical_sha256(view["source_view"]),
        "corpus_sha256": corpus_sha, "retrieval_summary_sha256": canonical_sha256(replay_summary),
        "retrieval_receipt_sha256": upstream["observation_sha256"], "capture_sha256": captured["capture_sha256"],
        "raw_receipt_sha256": raw["receipt_sha256"], "scorer_summary": summary,
        "scorer_summary_sha256": canonical_sha256(summary),
        "semantic_input_sha256": raw.get("semantic_input_sha256"),
        "generation_status": generation, "candidate_namespace": "CORPUS_CANDIDATE",
        "candidates": candidates, "source_payloads_base64": {k: base64.b64encode(v).decode("ascii") for k,v in sorted(used.items())},
        "generation_proof": proof, "labels": labels, "raw_scores": scores, "score_status": raw["status"],
        "score_provenance": "CAPTURE_STRUCTURAL_BINDING_ONLY_MODEL_REPLAY_REQUIRED",
        "probability_status": "NOT_AVAILABLE_UNCALIBRATED", "nil_probability": None, "selected_candidate_id": None,
        "truth_status": "UNJUDGED_NOT_ASSIGNED", "quality_status": "NOT_EVALUATED_UNSEEN_INPUT",
        "publication_authority": False, "public_apply": False, "central_db_write": False, "action_applied": False}
    result["graph_sha256"] = canonical_sha256(result)
    return _copy(result)


def validate_inference_graph(value, *, capture, corpus_snapshot: bytes, source_payloads: dict[str, bytes]) -> dict:
    """자체 SHA만 보지 않고 현재 capture/corpus/source로 전체 graph를 다시 만든다."""
    supplied = _copy(value)
    rebuilt = build_inference_graph(capture, corpus_snapshot=corpus_snapshot, source_payloads=source_payloads)
    _require(canonical_bytes(supplied) == canonical_bytes(rebuilt), "INFERENCE_GRAPH_REPLAY_MISMATCH")
    return rebuilt
