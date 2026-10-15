"""명시적 근거로 NIL raw logit을 CAL 학습 자료와 구형 FROZEN event에 연결한다.

``build_frozen_event_score``는 파일/모델/네트워크를 호출하지 않는다. example은
기존 learned preselection example의 네 필드이며 source_binding_sha256은
evidence_payloads 안의 별도 JSON 바이트를 가리킨다. 그 JSON은 아래
``_source_binding``의 exact projection이다. 공급자가 선언한 원문과 구형 graph의
연결을 바이트로 검산하며, 그 선언의 진실이나 상류 열거 완전성을 독립 입증하지
않는다. 일반 R2 runtime에 graph를 발명하거나 자동 삽입하지 않는다.

학습 manifest(TRAIN 포함)와 calibration manifest(TRAIN 제외)는 별도 SHA
인자로 고정한다. 반환 EventScoreVector에는 구형 calibration manifest SHA만
들어간다. 후보는 명시 ID 대응으로 구형 event 순서에 재배열하고 NIL은 마지막에
둔다. CAL은 별도 CalibrationFitEvent이며 기존 FROZEN enum과 지문은 유지한다.
교정 artifact/fit receipt/확률/선택/공개 판정은 만들지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

from ..promotion_gate import RetrievalState
from .candidate_generation import CandidateGenerationProof, candidate_generation_proof_from_dict
from .candidate_reranker_learned import _bind_example, _strict_capture
from .candidate_reranker_shadow import DIGEST_SCOPE, _FEATURE_CONTRACT
from .candidate_reranker_calibration_data import (
    CalibrationFitEvent, MAX_EVENTS, validate_calibration_fit_events,
)
from .candidate_set_calibration_shadow import CalibrationSplitManifest, EventScoreVector
from .candidate_set_shadow import NIL_LABEL, SelectiveShadowDecision, selective_shadow_from_dict
from .reranker_training_split import validate_training_split


SCHEMA_VERSION = "candidate_reranker_event_bridge_v1"
SOURCE_BINDING_SCHEMA = "candidate_reranker_event_source_binding_v1"
FEATURE_SCHEMA = "candidate_reranker_nil_features_v1"
FEATURE_SCHEMA_V2 = "candidate_reranker_nil_features_v2"
SEMANTIC_MODEL_FIELDS = ("feature_schema", "semantic_input_required",
                         "semantic_contract_sha256", "semantic_policy_sha256")
MAX_BYTES = 8 * 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MODEL_HASHES = ("model_manifest_sha256", "model_sha256", "scorer_sha256",
                 "feature_schema_sha256", "config_sha256", "training_split_manifest_sha256",
                 "candidate_ranker_model_sha256")
_MODEL_VALUES = ("backend", "data_kind", "training_status", "actual_model_available", "nil_head_available")


class EventBridgeError(ValueError):
    """부족하거나 모순된 연결 근거. 다른 상태/확률로 대체하지 않는다."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EventBridgeError(code)


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise EventBridgeError("JSON_INVALID") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _copy(value: Any, limit=MAX_BYTES) -> Any:
    raw = _bytes(value)
    _require(len(raw) <= limit, "BYTE_LIMIT")
    return json.loads(raw)


def _hash(value: Any) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value))


def _number(value: Any) -> float:
    _require(type(value) in (int, float), "FINITE_SCORE_REQUIRED")
    try:
        result = float(value)
    except OverflowError as exc:
        raise EventBridgeError("FINITE_SCORE_REQUIRED") from exc
    _require(math.isfinite(result), "FINITE_SCORE_REQUIRED")
    return result


def _payloads(source: Any, evidence: Any) -> tuple[dict, dict]:
    _require(isinstance(source, Mapping) and isinstance(evidence, Mapping), "PAYLOAD_MAP_REQUIRED")
    source, evidence = dict(source), dict(evidence)
    values = [*source.values(), *evidence.values()]
    _require(all(type(raw) is bytes for raw in values) and sum(map(len, values)) <= MAX_BYTES,
             "PAYLOAD_BYTES_LIMIT_OR_TYPE")
    return source, evidence


def _id_mapping(row: dict, view: dict, base: SelectiveShadowDecision) -> dict[str, str]:
    bridges = {item["corpus_candidate_id"]: item for item in row["r2_id_bridges"]}
    exposures = {item["candidate_id"]: item for item in row["exposures"]}
    mapping = {}
    for item in view["candidates"]:
        cid = item["candidate_id"]
        _require(item["event_eligible"] is True and item["identity_conflict"] is False
                 and item["option_kind"] == "WORK_CANDIDATE", "INELIGIBLE_RAW_EVENT")
        mapped = cid
        if view["candidate_namespace"] == "CORPUS_CANDIDATE":
            bridge = bridges.get(cid)
            _require(bridge is not None and bridge["status"] == "UNIQUE"
                     and len(bridge["candidate_ids"]) == 1, "EXPLICIT_UNIQUE_ID_BRIDGE_REQUIRED")
            mapped = bridge["candidate_ids"][0]
            _require(mapped in exposures and exposures[mapped]["corpus_candidate_id"] == cid,
                     "CORPUS_EXPOSURE_MISMATCH")
        _require(mapped in exposures and mapped not in mapping.values(), "ID_BRIDGE_NOT_BIJECTIVE")
        mapping[cid] = mapped
    eligible = [item.label for item in base.event_probabilities][:-1]
    _require(bool(mapping) and set(mapping.values()) == set(eligible)
             and set(mapping.values()) == set(exposures), "FULL_EVENT_SPACE_REQUIRED")
    return mapping


def semantic_model_fields(summary: dict) -> tuple[str, ...]:
    """새 모델의 정확한 feature/정책 조합만 허용한다. v1 projection은 유지한다."""
    if not any(key in summary for key in SEMANTIC_MODEL_FIELDS):
        return ()
    from .candidate_reranker_semantic_input import FEATURE_CONTRACT_SHA256
    from .candidate_reranker_semantics import POLICY_SHA256
    from . import candidate_reranker_learned as pairwise
    from . import candidate_reranker_nil_learned as nil
    module = nil if summary.get("backend") == nil.BACKEND else pairwise
    _require(summary.get("backend") in (nil.BACKEND, pairwise.BACKEND)
             and summary.get("feature_schema") == module.FEATURE_SCHEMA_V2
             and summary.get("semantic_input_required") is True
             and summary.get("semantic_contract_sha256") == FEATURE_CONTRACT_SHA256
             and summary.get("semantic_policy_sha256") == POLICY_SHA256
             and summary.get("feature_schema_sha256") == canonical_sha256({
                 "frozen_view_contract": _FEATURE_CONTRACT,
                 "learned_feature_contract": module._contract(module.FEATURE_SCHEMA_V2),
             }),
             "SEMANTIC_MODEL_CONTRACT_MISMATCH")
    return SEMANTIC_MODEL_FIELDS


def event_model_feature_schema(summary: dict) -> str:
    fields = semantic_model_fields(summary)
    _require(summary.get("backend") == "NIL_AUGMENTED_LINEAR_V1", "NIL_LEARNED_MODEL_REQUIRED")
    return FEATURE_SCHEMA_V2 if fields else FEATURE_SCHEMA


def resolve_example_semantic_input(example, row, source_payloads, evidence_payloads, *, split_manifest=None):
    """capture의 raw artifact 참조와 artifact 자체 지문을 혼용하지 않는다."""
    digest = example.get("capture_sha256")
    raw = evidence_payloads.get(digest)
    _require(_hash(digest) and type(raw) is bytes and hashlib.sha256(raw).hexdigest() == digest,
             "CAPTURE_BYTES_MISSING_OR_MISMATCH")
    capture = _strict_capture(raw)
    if capture.get("schema_version") == "reranker_preselection_capture_v1":
        return None
    from .candidate_reranker_semantic_input import resolve_training_semantic_input
    return resolve_training_semantic_input(capture, example["frozen_view"], row,
        source_payloads, evidence_payloads, split_manifest=split_manifest)


def validate_semantic_receipt(receipt, view, summary, semantic_input=None):
    """점수·실패 모두 소비 상태를 검산하고 공급된 artifact와 실제 소비 지문을 대조한다."""
    fields = semantic_model_fields(summary)
    if not fields:
        _require(not any(k in receipt for k in (*SEMANTIC_MODEL_FIELDS,
                 "semantic_input_sha256", "semantic_consumption")), "LEGACY_SEMANTIC_RECEIPT_FORBIDDEN")
        return
    _require(all(type(receipt.get(k)) is type(summary[k]) and receipt.get(k) == summary[k] for k in fields),
             "RECEIPT_SEMANTIC_MODEL_MISMATCH")
    value = receipt.get("semantic_consumption")
    keys = {"schema_version", "status", "reason_codes", "input_validated", "backend_invoked", "score_produced",
            "semantic_input_sha256", "semantic_contract_sha256", "semantic_observation_sha256",
            "semantic_policy_sha256", "scorer_input_sha256"}
    _require(type(value) is dict and set(value) == keys
             and value["schema_version"] == "candidate_reranker_semantic_consumption_v1"
             and "preselection_role_producer" not in receipt
             and all(type(value[k]) is bool for k in ("input_validated", "backend_invoked", "score_produced")),
             "SEMANTIC_CONSUMPTION_SCHEMA_INVALID")
    _require(value["reason_codes"] == receipt.get("reason_codes")
             and value["semantic_contract_sha256"] == summary["semantic_contract_sha256"]
             and value["semantic_policy_sha256"] == summary["semantic_policy_sha256"],
             "SEMANTIC_CONSUMPTION_POLICY_MISMATCH")
    scored = receipt.get("status") == "SCORED_LEARNED"
    valid, invoked = value["input_validated"], value["backend_invoked"]
    status = ("SCORED" if scored else "OUTPUT_LIMIT_EXCEEDED" if receipt.get("reason_codes") == ["RECEIPT_BYTE_LIMIT"]
              else "BACKEND_FAILED" if invoked else "INPUT_BOUND_NOT_SCORED" if valid else "NOT_CONSUMED")
    _require(value["status"] == status and value["score_produced"] is scored
             and (not invoked or valid) and (not scored or (valid and invoked)), "SEMANTIC_CONSUMPTION_STATE_INVALID")
    if valid:
        _require(all(_hash(value[k]) for k in ("semantic_input_sha256", "semantic_observation_sha256", "scorer_input_sha256"))
                 and value["scorer_input_sha256"] == receipt.get("input_sha256") == canonical_sha256(view)
                 and value["semantic_input_sha256"] == receipt.get("semantic_input_sha256")
                 and receipt.get("generation_status") == "COMPLETE", "SEMANTIC_CONSUMPTION_VIEW_MISMATCH")
        if semantic_input is not None:
            _require(value["semantic_input_sha256"] == semantic_input["input_sha256"]
                     and value["semantic_observation_sha256"] == canonical_sha256(semantic_input["observation"]),
                     "SEMANTIC_CONSUMPTION_ARTIFACT_MISMATCH")
    else:
        _require(receipt.get("semantic_input_sha256") is None and all(value[k] is None for k in
                 ("semantic_input_sha256", "semantic_observation_sha256", "scorer_input_sha256")),
                 "UNCONSUMED_SEMANTIC_INPUT_CONTRADICTION")


def _model(summary: dict, expected_sha: str, manifest: dict) -> None:
    _require(_hash(expected_sha) and canonical_sha256(summary) == expected_sha, "SCORER_SUMMARY_SHA_MISMATCH")
    _require(summary.get("schema_version") == "candidate_reranker_summary_v1"
             and summary.get("mode") == "SHADOW" and summary.get("status") == "AVAILABLE_LEARNED",
             "SCORER_SUMMARY_UNAVAILABLE")
    _require(all(_hash(summary.get(key)) for key in _MODEL_HASHES)
             and all(key in summary for key in _MODEL_VALUES), "MODEL_HASH_REQUIRED")
    _require(summary["backend"] == "NIL_AUGMENTED_LINEAR_V1"
             and summary["training_status"] == "TRAINED_PAIRWISE_PLUS_NIL_HEAD"
             and summary["actual_model_available"] is True and summary["nil_head_available"] is True,
             "NIL_LEARNED_MODEL_REQUIRED")
    _require(summary["training_split_manifest_sha256"] == manifest["manifest_sha256"],
             "MODEL_TRAINING_SPLIT_MISMATCH")
    _require(summary["data_kind"] == manifest["data_kind"], "MODEL_DATA_KIND_MISMATCH")
    _require(summary.get("manifest_sha256") == summary["model_manifest_sha256"], "MODEL_MANIFEST_ALIAS_MISMATCH")
    _require(all(summary.get(key) is False for key in ("publication_authority", "public_apply", "central_db_write"))
             and summary.get("probability_status") == "NOT_AVAILABLE_UNCALIBRATED", "SUMMARY_AUTHORITY_INVALID")
    event_model_feature_schema(summary)


def _scores(receipt: dict, view: dict, summary: dict, semantic_input=None) -> dict[str, float]:
    _require(receipt.get("schema_version") == "candidate_reranker_shadow_v1"
             and receipt.get("mode") == "SHADOW" and receipt.get("status") == "SCORED_LEARNED"
             and receipt.get("receipt_digest_scope") == DIGEST_SCOPE, "SCORED_RAW_RECEIPT_REQUIRED")
    _require(receipt.get("receipt_sha256") == canonical_sha256({k: v for k, v in receipt.items()
             if k not in {"receipt_sha256", "latency_ms", "binding"}}), "RECEIPT_SHA_MISMATCH")
    validate_semantic_receipt(receipt, view, summary, semantic_input)
    for key in (*_MODEL_HASHES, *_MODEL_VALUES):
        _require(type(receipt.get(key)) is type(summary[key]) and receipt.get(key) == summary[key],
                 "RECEIPT_MODEL_MISMATCH")
    _require(receipt.get("manifest_sha256") == summary["model_manifest_sha256"], "RECEIPT_MODEL_MISMATCH")
    _require(all(receipt.get(key) is False for key in ("publication_authority", "public_apply", "central_db_write"))
             and receipt.get("probability_status") == "NOT_AVAILABLE_UNCALIBRATED"
             and receipt.get("nil_probability") is None and receipt.get("selected_candidate_id") is None
             and receipt.get("operational_effect") == "NONE_SHADOW_ONLY", "RECEIPT_AUTHORITY_INVALID")
    expected = {"post_id": view["post_id"], "input_sha256": canonical_sha256(view),
        "query_sha256": canonical_sha256(view["source_view"]),
        "candidate_view_sha256": canonical_sha256(view["candidates"]),
        "candidate_set_fingerprint": view["candidate_set_fingerprint"],
        "generation_sha256": view["generation_sha256"], "generation_status": "COMPLETE",
        "candidate_namespace": view["candidate_namespace"],
        "candidate_option_bridge_status": "MISSING" if view["candidate_namespace"] == "CORPUS_CANDIDATE" else "NOT_REQUIRED"}
    _require(all(type(receipt.get(k)) is type(v) and receipt.get(k) == v for k, v in expected.items()),
             "RECEIPT_VIEW_MISMATCH")
    ids = [item["candidate_id"] for item in view["candidates"]]
    _require(receipt.get("frozen_candidate_ids") == ids, "RECEIPT_FROZEN_IDS_MISMATCH")
    _require(receipt.get("candidate_observations") == [{"candidate_id": c["candidate_id"],
             "role_observations": c["role_observations"]} for c in view["candidates"]], "RECEIPT_ROLES_MISMATCH")
    ranked, events = receipt.get("ranked_candidates"), receipt.get("event_logits")
    _require(type(ranked) is list and len(ranked) == len(ids)
             and type(events) is list and len(events) == len(ids) + 1, "RAW_EVENT_COUNT_MISMATCH")
    scores = {}
    for item in ranked:
        _require(type(item) is dict and set(item) == {"candidate_id", "score"}
                 and type(item["candidate_id"]) is str and item["candidate_id"] not in scores,
                 "RANKED_SCORE_SCHEMA_INVALID")
        scores[item["candidate_id"]] = _number(item["score"])
    _require(set(scores) == set(ids), "RAW_EVENT_ID_MISMATCH")
    _require(ranked == sorted(ranked, key=lambda item: (-item["score"], item["candidate_id"])),
             "RANK_ORDER_INVALID")
    scores[NIL_LABEL] = _number(receipt.get("nil_score"))
    for item, label in zip(events, [*ids, NIL_LABEL]):
        _require(type(item) is dict and set(item) == {"label", "score"} and item["label"] == label,
                 "RAW_EVENT_ORDER_INVALID")
        _require(_number(item["score"]) == scores[label], "RAW_EVENT_SCORE_MISMATCH")
    return scores


def _source_binding(*, example, row, view, receipt, summary, manifest, calibration,
                    base, proof, retrieval, mapping, publication_scope_id):
    # 한 SHA 영역을 다른 영역의 SHA로 덮지 않고 양쪽을 명시한다.
    value = {"schema_version": SOURCE_BINDING_SCHEMA, "stage": "PRE_SELECTION",
        "authority": "DECLARED_SOURCE_GRAPH_BINDING_NOT_INDEPENDENTLY_VERIFIED",
        "example_id": example["example_id"], "post_id": row["assignment"]["post_id"],
        "binding": {**row["binding"], "publication_scope_id": publication_scope_id},
        "source_spans_sha256": canonical_sha256(row["source_spans"]),
        "capture_sha256": example["capture_sha256"], "query_sha256": canonical_sha256(view["source_view"]),
        "frozen_view_sha256": canonical_sha256(view), "raw_receipt_sha256": receipt["receipt_sha256"],
        "scorer_summary_sha256": canonical_sha256(summary),
        "training_split_manifest_sha256": manifest["manifest_sha256"],
        "calibration_split_manifest_sha256": calibration.manifest_sha256,
        "base_shadow_fingerprint": base.shadow_fingerprint,
        "publication_input_fingerprint": base.input_fingerprint,
        "candidate_set_fingerprint": base.candidate_set.candidate_set_fingerprint,
        "observation_fingerprint": base.candidate_set.observation_fingerprint,
        "raw_generation_sha256": view["generation_sha256"],
        "generation_proof_fingerprint": proof.metadata_fingerprint,
        "retrieval_state_fingerprint": canonical_sha256(retrieval.to_dict()),
        "candidate_id_mapping": [{"raw_candidate_id": cid, "candidate_option_id": mapped}
                                 for cid, mapped in mapping.items()],
        "r2_id_bridges_sha256": canonical_sha256(row["r2_id_bridges"])}
    if semantic_model_fields(summary):
        value.update(schema_version="candidate_reranker_event_source_binding_v2",
                     semantic_input_sha256=receipt.get("semantic_input_sha256"))
    return value


def _prepare_context(*, scorer_summary: dict,
        expected_scorer_summary_sha256: str, training_manifest: dict,
        expected_training_manifest_sha256: str, calibration_manifest: CalibrationSplitManifest,
        expected_calibration_manifest_sha256: str, source_payloads: Mapping[str, bytes],
        evidence_payloads: Mapping[str, bytes]) -> dict:
    """전체 분할과 모델을 batch당 한 번 검산한다. 원본 자료를 수정하지 않는다."""
    _require(isinstance(calibration_manifest, CalibrationSplitManifest), "TYPED_GRAPH_REQUIRED")
    manifest, summary = map(_copy, (training_manifest, scorer_summary))
    _require(type(manifest) is dict and type(summary) is dict, "OBJECT_REQUIRED")
    payloads, evidence = _payloads(source_payloads, evidence_payloads)
    try:
        calibration = CalibrationSplitManifest(**{**calibration_manifest.__dict__,
            "split_fingerprints": dict(calibration_manifest.split_fingerprints)})
    except (ValueError, TypeError, KeyError) as exc:
        raise EventBridgeError("TYPED_GRAPH_INVALID") from exc
    _require(_hash(expected_training_manifest_sha256)
             and manifest.get("manifest_sha256") == expected_training_manifest_sha256,
             "TRAINING_MANIFEST_SHA_MISMATCH")
    validation = validate_training_split(manifest, source_payloads=payloads, evidence_payloads=evidence,
        calibration_manifest=calibration.to_dict(), expected_calibration_sha256=expected_calibration_manifest_sha256)
    _require(validation["ready_for_calibration_bridge"] is True, "TRAINING_CALIBRATION_BRIDGE_NOT_READY")
    _model(summary, expected_scorer_summary_sha256, manifest)
    return {"manifest": manifest, "summary": summary, "calibration": calibration,
            "payloads": payloads, "evidence": evidence}


def _validate_bound_event(context: dict, *, example: dict, raw_receipt: dict,
        base_shadow: SelectiveShadowDecision, generation_proof: CandidateGenerationProof,
        retrieval_state: RetrievalState, publication_scope_id: str, source_binding_sha256: str,
        required_split: str) -> dict:
    """CAL/FROZEN의 동일 원문·후보·점수·graph 검산. 정답은 점수와 분리한다."""
    _require(isinstance(base_shadow, SelectiveShadowDecision)
             and isinstance(generation_proof, CandidateGenerationProof)
             and isinstance(retrieval_state, RetrievalState), "TYPED_GRAPH_REQUIRED")
    _require(type(publication_scope_id) is str and 0 < len(publication_scope_id.strip()) <= 512,
             "PUBLICATION_SCOPE_REQUIRED")
    manifest, summary, calibration = (context[k] for k in ("manifest", "summary", "calibration"))
    payloads, evidence = context["payloads"], context["evidence"]
    example, receipt = _copy(example), _copy(raw_receipt, MAX_RECEIPT_BYTES)
    _require(type(example) is dict and type(receipt) is dict, "OBJECT_REQUIRED")
    try:
        base = selective_shadow_from_dict(_copy(base_shadow.to_dict()))
        proof = candidate_generation_proof_from_dict(_copy(generation_proof.to_ledger_dict()))
        retrieval = RetrievalState(**_copy(retrieval_state.to_dict()))
    except (ValueError, TypeError, KeyError) as exc:
        raise EventBridgeError("TYPED_GRAPH_INVALID") from exc
    rows = [row for row in manifest["rows"] if row["assignment"]["example_id"] == example.get("example_id")]
    _require(len(rows) == 1 and rows[0]["assignment"]["split"] == required_split,
             "FROZEN_ASSIGNMENT_REQUIRED" if required_split == "FROZEN_HOLDOUT" else "CAL_ASSIGNMENT_REQUIRED")
    row = rows[0]
    _require(base.probability_status == "NOT_AVAILABLE_UNCALIBRATED"
             and base.selected_label is None, "UNCALIBRATED_BASE_REQUIRED")
    _require(base.candidate_set.generation_status == proof.status == "COMPLETE"
             and base.candidate_set.candidate_set_recall_status == "READY_FOR_GOLD_EVALUATION"
             and base.candidate_set.integrity_status == "GO", "COMPLETE_ELIGIBLE_GRAPH_REQUIRED")
    _require(not retrieval.blocks_publish() and not {"retrieval_failclose_requires_abstain",
             "candidate_set_integrity_requires_abstain"}.intersection(base.reason_codes), "PUBLIC_GUARD_BLOCKED")
    _require(row["assignment"]["candidate_set_fingerprint"] == base.candidate_set.candidate_set_fingerprint,
             "BASE_CANDIDATE_SET_MISMATCH")
    try:
        semantic = event_model_feature_schema(summary) == FEATURE_SCHEMA_V2
        from .candidate_reranker_learned import FEATURE_SCHEMA_V2 as PAIRWISE_FEATURE_V2
        options = {"feature_schema": PAIRWISE_FEATURE_V2, "split_manifest": manifest} if semantic else {}
        view, _ = _bind_example(example, row, payloads, evidence, **options)
        semantic_input = resolve_example_semantic_input(example, row, payloads, evidence,
            split_manifest=manifest) if semantic else None
    except (ValueError, TypeError, KeyError) as exc:
        raise EventBridgeError(getattr(exc, "code", "PRESELECTION_BINDING_INVALID")) from exc
    _require(type(view["post_id"]) is type(row["assignment"]["post_id"]), "POST_ID_TYPE_MISMATCH")
    mapping = _id_mapping(row, view, base)
    scores = _scores(receipt, view, summary, semantic_input)
    if "binding" in receipt:
        expected = {**row["binding"], "post_id": row["assignment"]["post_id"],
            "publication_scope_id": publication_scope_id, "scope": "ATTEMPT_LOCAL_OBSERVATION"}
        _require(_bytes(receipt["binding"]) == _bytes(expected), "RECEIPT_STORAGE_BINDING_MISMATCH")
    _require(_hash(source_binding_sha256) and source_binding_sha256 in evidence,
             "SOURCE_GRAPH_BINDING_MISSING")
    raw = evidence[source_binding_sha256]
    _require(len(raw) <= MAX_RECEIPT_BYTES and hashlib.sha256(raw).hexdigest() == source_binding_sha256,
             "SOURCE_GRAPH_BINDING_SHA_MISMATCH")
    try:
        supplied = _strict_capture(raw)
    except ValueError as exc:
        raise EventBridgeError("SOURCE_GRAPH_BINDING_JSON_INVALID") from exc
    expected = _source_binding(example=example, row=row, view=view, receipt=receipt, summary=summary,
        manifest=manifest, calibration=calibration, base=base, proof=proof, retrieval=retrieval,
        mapping=mapping, publication_scope_id=publication_scope_id)
    _require(_bytes(supplied) == _bytes(expected), "SOURCE_GRAPH_BINDING_MISMATCH")
    remapped = {mapped: scores[cid] for cid, mapped in mapping.items()}
    remapped[NIL_LABEL] = scores[NIL_LABEL]
    labels = tuple(item.label for item in base.event_probabilities)
    return {"example_id": example["example_id"], "row": row, "base": base, "labels": labels,
        "raw_scores": tuple(remapped[label] for label in labels), "receipt": receipt,
        "generation_proof_fingerprint": proof.metadata_fingerprint,
        "retrieval_state_fingerprint": canonical_sha256(retrieval.to_dict()),
        "feature_fingerprint": canonical_sha256({
            "schema_version": "candidate_reranker_event_bridge_v2" if semantic else SCHEMA_VERSION,
            "feature_schema_sha256": summary["feature_schema_sha256"],
            "frozen_view_sha256": canonical_sha256(view), "source_binding_sha256": source_binding_sha256})}


def build_frozen_event_score(*, example: dict, raw_receipt: dict, scorer_summary: dict,
        expected_scorer_summary_sha256: str, training_manifest: dict,
        expected_training_manifest_sha256: str, calibration_manifest: CalibrationSplitManifest,
        expected_calibration_manifest_sha256: str, source_payloads: Mapping[str, bytes],
        evidence_payloads: Mapping[str, bytes], base_shadow: SelectiveShadowDecision,
        generation_proof: CandidateGenerationProof, retrieval_state: RetrievalState,
        publication_scope_id: str, source_binding_sha256: str) -> EventScoreVector:
    """기존 v1 FROZEN 서명·event 순서·feature/score 지문을 보존한다."""
    context = _prepare_context(scorer_summary=scorer_summary,
        expected_scorer_summary_sha256=expected_scorer_summary_sha256, training_manifest=training_manifest,
        expected_training_manifest_sha256=expected_training_manifest_sha256, calibration_manifest=calibration_manifest,
        expected_calibration_manifest_sha256=expected_calibration_manifest_sha256,
        source_payloads=source_payloads, evidence_payloads=evidence_payloads)
    bound = _validate_bound_event(context, example=example, raw_receipt=raw_receipt,
        base_shadow=base_shadow, generation_proof=generation_proof, retrieval_state=retrieval_state,
        publication_scope_id=publication_scope_id, source_binding_sha256=source_binding_sha256,
        required_split="FROZEN_HOLDOUT")
    return EventScoreVector.create(example_id=bound["example_id"], post_id=bound["row"]["assignment"]["post_id"],
        split="FROZEN_HOLDOUT", base_shadow=bound["base"], raw_scores=bound["raw_scores"],
        scorer_fingerprint=context["summary"]["scorer_sha256"],
        split_manifest_sha256=context["calibration"].manifest_sha256,
        generation_proof_fingerprint=bound["generation_proof_fingerprint"],
        retrieval_state_fingerprint=bound["retrieval_state_fingerprint"],
        feature_schema_version=event_model_feature_schema(context["summary"]), feature_fingerprint=bound["feature_fingerprint"])


def build_calibration_fit_events(rows, expected_example_ids, *, scorer_summary: dict,
        expected_scorer_summary_sha256: str, training_manifest: dict,
        expected_training_manifest_sha256: str, calibration_manifest: CalibrationSplitManifest,
        expected_calibration_manifest_sha256: str, source_payloads: Mapping[str, bytes],
        evidence_payloads: Mapping[str, bytes]) -> tuple[CalibrationFitEvent, ...]:
    """전체 CAL 행만 반환한다. 누락/실패 행 필터링과 TRAIN/FROZEN 혼입을 거절한다.

    rows는 example/raw_receipt/base_shadow/generation_proof/retrieval_state/
    publication_scope_id/source_binding_sha256의 exact 7필드 목록이다.
    CAL example_id 오름차순을 외부 expected_example_ids 및 rows 순서와 대조한다.
    원문 fragment/후보 순서는 각 행에서 그대로 검산하며 다시 정렬하지 않는다.
    """
    _require(type(rows) in (list, tuple) and 1 <= len(rows) <= MAX_EVENTS, "CAL_ROW_COUNT_LIMIT")
    _require(type(expected_example_ids) in (list, tuple) and 1 <= len(expected_example_ids) <= MAX_EVENTS
             and all(type(x) is str and x.strip() for x in expected_example_ids), "EXPECTED_CAL_IDS_REQUIRED")
    fields = {"example", "raw_receipt", "base_shadow", "generation_proof", "retrieval_state",
              "publication_scope_id", "source_binding_sha256"}
    _require(all(type(row) is dict and set(row) == fields and type(row["example"]) is dict for row in rows),
             "CAL_ROW_FIELDS_INVALID")
    context = _prepare_context(scorer_summary=scorer_summary,
        expected_scorer_summary_sha256=expected_scorer_summary_sha256, training_manifest=training_manifest,
        expected_training_manifest_sha256=expected_training_manifest_sha256, calibration_manifest=calibration_manifest,
        expected_calibration_manifest_sha256=expected_calibration_manifest_sha256,
        source_payloads=source_payloads, evidence_payloads=evidence_payloads)
    expected = sorted(r["assignment"]["example_id"] for r in context["manifest"]["rows"]
                      if r["assignment"]["split"] == "CALIBRATION")
    calibration_ids = sorted(a.example_id for a in context["calibration"].assignments if a.split == "CALIBRATION")
    supplied = [r["example"].get("example_id") for r in rows]
    _require(expected == calibration_ids == list(expected_example_ids) == supplied, "CAL_FULL_UNIVERSE_REQUIRED")
    events, summary = [], context["summary"]
    for item in rows:
        bound = _validate_bound_event(context, **item, required_split="CALIBRATION")
        assignment, base = bound["row"]["assignment"], bound["base"]
        events.append(CalibrationFitEvent.create(example_id=bound["example_id"], post_id=assignment["post_id"],
            labels=bound["labels"], raw_scores=bound["raw_scores"], truth_kind=assignment["truth_kind"],
            truth_label=assignment["truth_label"], label_provenance=bound["row"]["label_provenance"],
            training_split_manifest_sha256=context["manifest"]["manifest_sha256"],
            calibration_manifest_sha256=context["calibration"].manifest_sha256,
            scorer_fingerprint=summary["scorer_sha256"], scorer_summary_sha256=canonical_sha256(summary),
            model_sha256=summary["model_sha256"], base_model_sha256=summary["candidate_ranker_model_sha256"],
            data_kind=summary["data_kind"], source_binding_sha256=item["source_binding_sha256"],
            raw_receipt_sha256=bound["receipt"]["receipt_sha256"],
            candidate_set_fingerprint=base.candidate_set.candidate_set_fingerprint,
            publication_input_fingerprint=base.input_fingerprint,
            generation_proof_fingerprint=bound["generation_proof_fingerprint"],
            retrieval_state_fingerprint=bound["retrieval_state_fingerprint"],
            feature_fingerprint=bound["feature_fingerprint"]))
    return validate_calibration_fit_events(events, expected_example_ids=expected_example_ids)
