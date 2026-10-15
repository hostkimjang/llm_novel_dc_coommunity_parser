"""전체 FROZEN raw 분모와 고정 NIL/CAL graph의 순수 서술 평가.

원문 결속은 annotation 진실의 독립 검증이 아니다. 파일/모델/새 fit 호출 없이
이미 고정한 artifact를 소비한다. 실제 readback·baseline 품질 승인은 지원하지
않으며 SOURCE_BACKED에도 품질 수용을 주장하지 않는다.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import re
from typing import Mapping

from . import candidate_reranker_evaluation as raw_evaluation
from ..grounding import candidate_reranker_event_bridge as bridge
from ..grounding import candidate_set_calibration_shadow as calibration
from ..grounding.candidate_generation import CandidateGenerationProof, candidate_generation_proof_from_dict
from ..grounding.candidate_set_shadow import SelectiveShadowDecision, selective_shadow_from_dict
from ..grounding.candidate_reranker_learned import _strict_capture
from ..grounding.reranker_training_split import validate_training_split
from ..promotion_gate import RetrievalState

SCHEMA = "candidate_reranker_nil_evaluation_v1"
MAX_ROWS = 256
MAX_BYTES = 16 * 1024 * 1024
GRAPH_KEYS = frozenset({"example", "raw_receipt", "base_shadow", "generation_proof",
                        "retrieval_state", "publication_scope_id", "source_binding_sha256"})
canonical_sha256 = raw_evaluation.canonical_sha256


class NilEvaluationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise NilEvaluationError(code)


def _copy(value):
    return raw_evaluation._copy(value)


def _same(left, right):
    return raw_evaluation._bytes(left) == raw_evaluation._bytes(right)


def _unavailable_model_receipt(receipt, summary, view):
    if receipt.get("status") not in ("UNAVAILABLE_MODEL", "NOT_SCORED_GENERATION_UNKNOWN",
            "NOT_SCORED_GENERATION_TRUNCATED", "EMPTY_CANDIDATE_SET", "EMPTY_QUERY") \
            or receipt.get("actual_model_available") is not False:
        return False
    from ..grounding import candidate_reranker_shadow as adapter
    view = adapter._validate_view(_copy(view))
    reasons = receipt.get("reason_codes")
    _require(type(reasons) is list and len(reasons) == 1 and type(reasons[0]) is str
             and re.fullmatch(r"[A-Z0-9_]{1,96}", reasons[0]) is not None, "UNAVAILABLE_MODEL_REASON_INVALID")
    # scorer.score 호출 없이 실제 adapter의 미가용 summary/receipt 생성 계약만
    # 재구성한다. 미가용 adapter SHA를 학습된 scorer SHA로 오인하지 않는다.
    # 실제 score()는 가용성보다 generation/빈 후보/빈 query를 먼저 판정한다.
    if view["generation_status"] != "COMPLETE":
        status, expected_reasons = "NOT_SCORED_GENERATION_" + view["generation_status"], ["GENERATION_" + view["generation_status"]]
        runtime_reason = "GENERATION_" + view["generation_status"]
    elif not view["candidates"]:
        status, expected_reasons, runtime_reason = "EMPTY_CANDIDATE_SET", ["NO_FROZEN_CANDIDATES"], "EMPTY_CANDIDATE_SET"
    elif not any(p["text"].strip() for p in view["source_view"]["fragments"]):
        status, expected_reasons, runtime_reason = "EMPTY_QUERY", ["NO_SOURCE_TEXT"], "EMPTY_QUERY"
    else:
        status, expected_reasons, runtime_reason = "UNAVAILABLE_MODEL", reasons, None
    _require(receipt["status"] == status and reasons == expected_reasons, "UNAVAILABLE_MODEL_BRANCH_MISMATCH")
    unavailable = adapter._summary(summary["model_manifest_sha256"], reason=reasons[0])
    template = adapter._receipt(unavailable, status=status, reasons=expected_reasons,
                                started=0.0, view=view)
    if "preselection_role_producer" in receipt:
        from ..runtime.candidate_reranker import _attach_roles, _role_not_executed
        from ..grounding.candidate_reranker_roles import validate_metadata
        metadata = validate_metadata(receipt["preselection_role_producer"])
        if metadata["status"] in ("OBSERVED", "NO_MATCH", "AMBIGUOUS"):
            _require(runtime_reason is None, "UNAVAILABLE_ROLE_EXECUTION_ORDER")
            metadata = validate_metadata(metadata, frozen_view=view)
        else:
            allowed = [_role_not_executed("EXPLICIT_FROZEN_VIEW_PROVIDED")]
            if runtime_reason is not None:
                allowed.append(_role_not_executed(runtime_reason))
            _require(any(_same(metadata, value) for value in allowed), "UNAVAILABLE_ROLE_NONEXECUTION_INVALID")
        template = _attach_roles(template, metadata)
    body = lambda r: {k: v for k, v in r.items() if k not in {"binding", "latency_ms"}}
    _require(_same(body(receipt), body(template)), "UNAVAILABLE_MODEL_TEMPLATE_MISMATCH")
    return True


def _terminal_model(receipt, summary, view):
    """미가용 값은 명시 한계로 남기되 알려진 모델/점수 모순은 거절한다."""
    if receipt["status"] == "SCORED_LEARNED":
        bridge._scores(receipt, view, summary)
    elif not _unavailable_model_receipt(receipt, summary, view):
        for key in bridge._MODEL_HASHES + bridge._MODEL_VALUES + (
                "manifest_sha256", "model_kind", "model_quality_status"):
            value = receipt.get(key)
            if value is not None and not (key in ("backend", "data_kind") and value == "UNAVAILABLE"):
                _require(type(value) is type(summary.get(key)) and value == summary.get(key),
                         "TERMINAL_MODEL_CONTRADICTION")
        _require(receipt.get("nil_score") is None and receipt.get("event_logits") in (None, []),
                 "UNSCORED_WITH_NIL_LOGITS")
        roles = receipt.get("candidate_observations")
        if roles not in (None, []):
            _require(_same(roles, [{"candidate_id": c["candidate_id"],
                "role_observations": c["role_observations"]} for c in view["candidates"]]),
                "TERMINAL_ROLE_CONTRADICTION")
    for key in ("model_kind", "model_quality_status"):
        if receipt.get(key) is not None:
            _require(receipt[key] == summary.get(key), "MODEL_KIND_CONTRADICTION")
    if "preselection_role_producer" in receipt:
        from ..runtime.candidate_reranker import _valid_role_metadata
        _require(_valid_role_metadata(receipt), "ROLE_PRODUCER_METADATA_INVALID")


def _observation(expected, observed, row, model, payloads, evidence, summary, *, split_manifest=None):
    _require(type(expected) is dict and set(expected) == {"example_id", "publication_scope_id", "frozen_view",
        "candidate_text_bindings", "capture_sha256"}, "EXPECTED_ROW_SCHEMA")
    receipt = observed.get("receipt") if type(observed) is dict else None
    if type(receipt) is dict and receipt.get("status") == "UNAVAILABLE_MODEL":
        raw_evaluation._validate_view(_copy(expected["frozen_view"]))
    if type(receipt) is dict and _unavailable_model_receipt(receipt, summary, expected["frozen_view"]):
        translated = _copy(observed)
        for key in raw_evaluation.HASH_FIELDS:
            if key != "model_manifest_sha256":
                translated["receipt"][key] = None
        translated["receipt"]["receipt_sha256"] = canonical_sha256({k: v for k, v in translated["receipt"].items()
            if k not in {"receipt_sha256", "latency_ms", "binding"}})
        result = raw_evaluation._observation(expected, translated, row, model, payloads, evidence,
                                             split_manifest=split_manifest)
        result["receipt_sha256"] = receipt["receipt_sha256"]
        result["binding_limits"].append("MODEL_NOT_LOADED_MANIFEST_PIN_ONLY")
        return result
    known_unobserved = type(receipt) is dict and receipt.get("status") == "NOT_AVAILABLE" and receipt.get("reason_codes") in (
        ["PIPELINE_NOT_EXECUTED"], ["RECEIPT_NOT_AVAILABLE"], ["INVALID_OR_OVERSIZED_RECEIPT"])
    sentinel = known_unobserved or (type(receipt) is dict and receipt.get("status") in
        ("NOT_AVAILABLE", "ERROR", "LIMIT_EXCEEDED", "INVALID_INPUT", "NOT_SCORED_GENERATION_UNKNOWN",
         "NOT_SCORED_EMPTY_CORPUS", "EMPTY_QUERY") and receipt.get("generation_status") == "UNKNOWN"
        and receipt.get("generation_sha256") is None and receipt.get("input_sha256") is None
        and receipt.get("candidate_view_sha256") is None)
    if not sentinel:
        return raw_evaluation._observation(expected, observed, row, model, payloads, evidence,
                                           split_manifest=split_manifest)
    # 원래 receipt 전체를 실제 exporter의 미관측 구조와 먼저 대조한다. UNKNOWN은
    # expected COMPLETE와 다른 관측이 아니라 '관측 자체 없음'일 때만 허용한다.
    from ..runtime.candidate_reranker import _unavailable
    reasons = receipt.get("reason_codes")
    _require(type(reasons) is list and len(reasons) == 1 and type(reasons[0]) is str
             and re.fullmatch(r"[A-Z0-9_]{1,96}", reasons[0]) is not None, "UNOBSERVED_REASON_INVALID")
    query = receipt.get("query_sha256")
    _require(query is None or query == canonical_sha256(expected["frozen_view"]["source_view"]),
             "UNOBSERVED_QUERY_CONTRADICTION")
    if receipt["status"] == "EMPTY_QUERY":
        _require(not any(p["text"].strip() for p in expected["frozen_view"]["source_view"]["fragments"]),
                 "FALSE_EMPTY_QUERY")
    template = _unavailable(reasons[0], row["assignment"]["post_id"], summary,
                            status=receipt["status"], query_sha256=query)
    body = lambda r: {k: v for k, v in r.items() if k not in {"binding", "latency_ms"}}
    _require(_same(body(receipt), body(template)), "UNOBSERVED_SENTINEL_CONTRADICTION")
    translated = _copy(observed)
    translated["receipt"]["generation_status"] = None
    translated["receipt"]["candidate_namespace"] = None
    translated["receipt"]["status"] = "NOT_AVAILABLE"
    translated["receipt"]["receipt_sha256"] = canonical_sha256({k: v for k, v in translated["receipt"].items()
        if k not in {"receipt_sha256", "latency_ms", "binding"}})
    result = raw_evaluation._observation(expected, translated, row, model, payloads, evidence,
                                         split_manifest=split_manifest)
    result.update(receipt_sha256=receipt["receipt_sha256"], source_terminal=receipt["status"], generation_status="UNKNOWN",
                  expected_generation_status=expected["frozen_view"]["generation_status"], gold_present=None)
    result["binding_limits"].append("GENERATION_NOT_OBSERVED")
    return result


def _graph_payload(graph):
    _require(type(graph) is dict and set(graph) == GRAPH_KEYS, "GRAPH_ROW_SCHEMA")
    _require(isinstance(graph["base_shadow"], SelectiveShadowDecision)
             and isinstance(graph["generation_proof"], CandidateGenerationProof)
             and isinstance(graph["retrieval_state"], RetrievalState), "TYPED_GRAPH_REQUIRED")
    return {**graph, "base_shadow": graph["base_shadow"].to_dict(),
        "generation_proof": graph["generation_proof"].to_ledger_dict(),
        "retrieval_state": graph["retrieval_state"].to_dict()}


def _bind_graph(graph, expected, observation, row, context):
    """불완전 graph도 공급한 source 결속은 검산하고, 완전성은 별도 판정한다."""
    example = {k: v for k, v in expected.items() if k != "publication_scope_id"}
    _require(_same(graph["example"], example)
             and graph["publication_scope_id"] == expected["publication_scope_id"], "GRAPH_EXAMPLE_MISMATCH")
    receipt = observation["receipt"]
    _require(type(graph["raw_receipt"]) is dict, "GRAPH_RAW_REQUIRED")
    raw_body = lambda r: {k: v for k, v in r.items() if k not in {"binding", "latency_ms"}}
    _require(_same(raw_body(graph["raw_receipt"]), raw_body(receipt)), "GRAPH_RAW_MISMATCH")
    if "binding" in graph["raw_receipt"]:
        _require(_same(graph["raw_receipt"]["binding"], receipt["binding"]), "GRAPH_STORAGE_BINDING")
    base = selective_shadow_from_dict(graph["base_shadow"])
    proof = candidate_generation_proof_from_dict(graph["generation_proof"])
    retrieval = RetrievalState(**graph["retrieval_state"])
    _require(base.probability_status == "NOT_AVAILABLE_UNCALIBRATED" and base.selected_label is None,
             "UNCALIBRATED_BASE_REQUIRED")
    _require(base.candidate_set.candidate_set_fingerprint == row["assignment"]["candidate_set_fingerprint"],
             "BASE_CANDIDATE_SET_MISMATCH")
    view = expected["frozen_view"]
    mapping = raw_evaluation._id_mapping(row, view)
    digest = graph["source_binding_sha256"]
    evidence = context["evidence_payloads"]
    _require(bridge._hash(digest) and digest in evidence, "SOURCE_GRAPH_BINDING_MISSING")
    payload = evidence[digest]
    _require(len(payload) <= bridge.MAX_RECEIPT_BYTES
             and hashlib.sha256(payload).hexdigest() == digest, "SOURCE_GRAPH_BINDING_SHA_MISMATCH")
    supplied = _strict_capture(payload)
    target = bridge._source_binding(example=example, row=row, view=view, receipt=receipt,
        summary=context["scorer_summary"], manifest=context["training_manifest"],
        calibration=context["calibration_manifest"], base=base, proof=proof, retrieval=retrieval,
        mapping=mapping, publication_scope_id=expected["publication_scope_id"])
    _require(_same(supplied, target), "SOURCE_GRAPH_BINDING_MISMATCH")
    reasons = []
    if base.candidate_set.generation_status != "COMPLETE" or proof.status != "COMPLETE":
        reasons.append("GENERATION_INCOMPLETE")
    if base.candidate_set.candidate_set_recall_status != "READY_FOR_GOLD_EVALUATION":
        reasons.append("CANDIDATE_RECALL_UNAVAILABLE")
    if base.candidate_set.integrity_status != "GO":
        reasons.append("CANDIDATE_SET_INTEGRITY")
    if retrieval.blocks_publish() or {"retrieval_failclose_requires_abstain",
            "candidate_set_integrity_requires_abstain"}.intersection(base.reason_codes):
        reasons.append("SOURCE_GUARD_BLOCKED")
    eligible = {item.label for item in base.event_probabilities if item.label != "__NIL__"}
    if set(mapping.values()) != eligible or set(mapping.values()) != {e["candidate_id"] for e in row["exposures"]}:
        reasons.append("INCOMPLETE_EVENT_SPACE")
    if any(c["event_eligible"] is not True or c["identity_conflict"] is not False
           or c["option_kind"] != "WORK_CANDIDATE" for c in view["candidates"]):
        reasons.append("INELIGIBLE_RAW_EVENT")
    return {"example": example, "raw_receipt": receipt, "base_shadow": base,
        "generation_proof": proof, "retrieval_state": retrieval,
        "publication_scope_id": expected["publication_scope_id"], "source_binding_sha256": digest}, reasons


def _rank_metrics(rows):
    # 후보만의 순위 통계다. __NIL__ logit을 후보 MRR에 삽입하지 않는다.
    work = [r for r in rows if r["truth_kind"] == "CANDIDATE"]
    scored = [r for r in work if r["scored"]]
    known = [r for r in work if r["gold_present"] is not None]
    present = [r for r in work if r["gold_present"] is True]
    present_scored = [r for r in present if r["scored"]]
    rr = sum(r["reciprocal_rank"] for r in scored)
    top = sum(r["ranked_candidate_ids"][0] == r["truth_label"] for r in present_scored)
    metric = raw_evaluation._metric
    return {"mrr_scored_work": metric(rr, len(scored)),
        "mrr_all_work_operational": metric(rr, len(work), status="ACCOUNTING_ONLY_UNAVAILABLE_AS_ZERO"),
        "candidate_recall": metric(sum(r["gold_present"] is True for r in known), len(known),
                                    status="COMPLETE_FROZEN_CANDIDATE_SET_ONLY"),
        "candidate_recall_operational": metric(len(present), len(work), status="ACCOUNTING_ONLY_UNKNOWN_AS_MISS"),
        "gold_present_top1_accuracy": metric(top, len(present_scored)),
        "gold_present_top1_all_terminals": metric(top, len(present), status="ACCOUNTING_ONLY_UNAVAILABLE_AS_ZERO"),
        "score_coverage": metric(sum(r["scored"] for r in rows), len(rows))}


def evaluate_frozen_nil_scores(*, training_manifest: dict, expected_training_manifest_sha256: str,
        source_payloads: Mapping[str, bytes], evidence_payloads: Mapping[str, bytes],
        expected_rows: list[dict], observations: list[dict], scorer_summary: dict,
        expected_scorer_summary_sha256: str, calibration_manifest: calibration.CalibrationSplitManifest,
        expected_calibration_manifest_sha256: str, policy: calibration.CalibrationEvaluationPolicy,
        calibration_artifact: calibration.CalibrationArtifact | None, frozen_rows: list[dict],
        expected_policy_sha256: str | None = None, expected_artifact_sha256: str | None = None,
        evidence_mode: str = "SYNTHETIC_CONTRACT_ONLY") -> dict:
    """전체 raw 관측 필수, 순서를 유지한 graph 부분집합 허용. 입력과 파일 불변.

    실제 readback을 받지 않으므로 FROZEN_ACTUAL 요청은 서술 분모만 반환한다.
    공용 typed artifact 검산이 CAL fit 증거를 재계산할 수 있으나 새 fit은 없다.
    """
    _require(evidence_mode in ("SYNTHETIC_CONTRACT_ONLY", "FROZEN_ACTUAL"), "EVIDENCE_MODE_INVALID")
    _require(type(expected_rows) is list and type(observations) is list
             and 0 < len(expected_rows) <= MAX_ROWS and len(observations) == len(expected_rows), "ROW_LIMIT_OR_COUNT")
    _require(type(frozen_rows) is list and len(frozen_rows) <= len(expected_rows), "GRAPH_LIMIT_OR_TYPE")
    _require(isinstance(calibration_manifest, calibration.CalibrationSplitManifest)
             and isinstance(policy, calibration.CalibrationEvaluationPolicy), "TYPED_CONTEXT_REQUIRED")
    _require(calibration_artifact is None or isinstance(calibration_artifact, calibration.CalibrationArtifact),
             "TYPED_ARTIFACT_REQUIRED")
    graph_payloads = [_graph_payload(g) for g in frozen_rows]
    snapshot = _copy({"manifest": training_manifest, "expected": expected_rows, "observed": observations,
        "summary": scorer_summary, "graphs": graph_payloads, "calibration": calibration_manifest.to_dict(),
        "policy": policy.to_dict(), "artifact": calibration_artifact.to_dict() if calibration_artifact is not None else None})
    manifest, expected, observed, summary, graphs = (snapshot[k] for k in ("manifest", "expected", "observed", "summary", "graphs"))
    _require(type(manifest) is dict and type(summary) is dict, "OBJECT_REQUIRED")
    payloads, evidence = bridge._payloads(source_payloads, evidence_payloads)
    cal_value = snapshot["calibration"]
    cal_value["assignments"] = tuple(calibration.CalibrationSplitAssignment(**a) for a in cal_value["assignments"])
    cal_manifest = calibration.CalibrationSplitManifest(**cal_value)
    policy = calibration.CalibrationEvaluationPolicy(**snapshot["policy"])
    _require(manifest.get("manifest_sha256") == expected_training_manifest_sha256
             and bridge._hash(expected_training_manifest_sha256), "TRAINING_MANIFEST_SHA_MISMATCH")
    _require(cal_manifest.manifest_sha256 == expected_calibration_manifest_sha256,
             "CALIBRATION_MANIFEST_SHA_MISMATCH")
    if expected_policy_sha256 is not None:
        _require(policy.policy_sha256 == expected_policy_sha256, "POLICY_SHA_MISMATCH")
    validation = validate_training_split(manifest, source_payloads=payloads, evidence_payloads=evidence,
        calibration_manifest=cal_manifest.to_dict(), expected_calibration_sha256=expected_calibration_manifest_sha256)
    _require(validation["status"] != "INVALID", "TRAINING_SPLIT_INVALID")
    bridge._model(summary, expected_scorer_summary_sha256, manifest)
    model = {k: summary[k] for k in raw_evaluation.MODEL_FIELDS + bridge.semantic_model_fields(summary)}
    assignments = [r for r in manifest["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT"]
    ids = [r["assignment"]["example_id"] for r in assignments]
    _require(ids and all(type(r) is dict for r in expected + observed)
             and [r.get("example_id") for r in expected] == ids
             and [r.get("example_id") for r in observed] == ids, "FULL_FROZEN_UNIVERSE_ORDER_REQUIRED")
    graph_ids = [g["example"].get("example_id") if type(g["example"]) is dict else None for g in graphs]
    _require(all(type(eid) is str and eid in ids for eid in graph_ids)
             and len(set(graph_ids)) == len(graph_ids)
             and graph_ids == [eid for eid in ids if eid in graph_ids], "GRAPH_UNIVERSE_ORDER_REQUIRED")
    graph_by_id = dict(zip(graph_ids, graphs))
    artifact = None
    if snapshot["artifact"] is not None:
        _require(isinstance(calibration_artifact, calibration.CalibrationArtifact), "TYPED_ARTIFACT_REQUIRED")
        artifact = calibration.calibration_artifact_from_dict(snapshot["artifact"])
        _require(artifact.schema_version == "candidate_set_calibration_artifact_v2", "LEARNED_CAL_ARTIFACT_V2_REQUIRED")
        artifact.validate_against(cal_manifest, policy)
        if expected_artifact_sha256 is not None:
            _require(artifact.artifact_sha256 == expected_artifact_sha256, "ARTIFACT_SHA_MISMATCH")
        binding = {"training_split_manifest_sha256": manifest["manifest_sha256"],
            "calibration_manifest_sha256": cal_manifest.manifest_sha256, "scorer_fingerprint": summary["scorer_sha256"],
            "scorer_summary_sha256": expected_scorer_summary_sha256, "model_sha256": summary["model_sha256"],
            "base_model_sha256": summary["candidate_ranker_model_sha256"], "data_kind": summary["data_kind"]}
        _require(_same(artifact.fit_receipt.to_dict()["learning_evidence"]["binding"], binding),
                 "ARTIFACT_MODEL_TRAIN_BINDING_MISMATCH")
    else:
        _require(expected_artifact_sha256 is None, "MISSING_PINNED_ARTIFACT")
    common = {"training_manifest": manifest, "expected_training_manifest_sha256": expected_training_manifest_sha256,
        "calibration_manifest": cal_manifest, "expected_calibration_manifest_sha256": expected_calibration_manifest_sha256,
        "scorer_summary": summary, "expected_scorer_summary_sha256": expected_scorer_summary_sha256,
        "source_payloads": payloads, "evidence_payloads": evidence}
    rows, shadows, bases, vectors = [], {}, {}, {}
    for exp, obs, assignment in zip(expected, observed, assignments):
        row = _observation(exp, obs, assignment, model, payloads, evidence, summary,
                           split_manifest=manifest)
        _terminal_model(obs["receipt"], summary, exp["frozen_view"])
        reasons = []
        graph = graph_by_id.get(row["example_id"])
        bound = None
        if graph is None:
            reasons.append("SOURCE_GRAPH_MISSING")
        else:
            bound, graph_reasons = _bind_graph(graph, exp, obs, assignment, common)
            reasons.extend(graph_reasons)
        if not row["scored"]:
            reasons.append("RAW_TERMINAL_" + row["source_terminal"])
        if row["gold_present"] is False:
            reasons.append("GOLD_CANDIDATE_NOT_RETRIEVED")
        if artifact is None:
            reasons.append("CALIBRATION_ARTIFACT_MISSING")
        if validation["ready_for_calibration_bridge"] is not True:
            reasons.append("TRAINING_CALIBRATION_BRIDGE_NOT_READY")
        if row["truth_kind"] == "UNJUDGED":
            reasons.append("UNJUDGED_FROZEN_ROW")
        shadow = None
        if not reasons:
            vector = bridge.build_frozen_event_score(**common, **bound)
            shadow = calibration.build_calibration_shadow(base_shadow=bound["base_shadow"],
                score_vector=vector, artifact=artifact, split_manifest=cal_manifest, policy=policy,
                assignment=next(a for a in cal_manifest.assignments if a.example_id == row["example_id"]))
            eid = row["example_id"]
            shadows[eid], bases[eid], vectors[eid] = shadow, bound["base_shadow"], vector
        row.update(graph_status="MISSING" if graph is None else "BOUND",
            calibration_status="BOUND" if shadow is not None else "NOT_EVALUABLE",
            calibration_reason_codes=reasons, calibration_shadow=shadow.to_dict() if shadow else None,
            action=shadow.action if shadow else ("ABSTAIN" if row["source_terminal"] == "EMPTY_CANDIDATE_SET" else "UNAVAILABLE"),
            action_applied=False, observed_model_binding={k: obs["receipt"].get(k)
                for k in bridge._MODEL_HASHES + bridge._MODEL_VALUES})
        rows.append(row)
    reasons = []
    if len(shadows) != len(rows):
        reasons.append("INCOMPLETE_FROZEN_CALIBRATION_UNIVERSE")
    if evidence_mode == "FROZEN_ACTUAL" or summary["data_kind"] != "SYNTHETIC_FIXTURE":
        reasons.append("ACTUAL_READBACK_AND_BASELINE_NOT_SUPPORTED")
    if reasons:
        evaluated = calibration._early_evaluation(status="NOT_EVALUABLE", reason=";".join(reasons), frozen_count=len(rows))
    else:
        evaluated = calibration.evaluate_frozen_holdout(split_manifest=cal_manifest, shadows=shadows,
            policy=policy, evidence_mode="SYNTHETIC_CONTRACT_ONLY", base_shadows=bases,
            score_vectors=vectors, calibration_artifact=artifact)
    report = {"schema_version": SCHEMA, "status": "DESCRIPTIVE_EVALUATION_COMPLETE" if not reasons else "NOT_EVALUABLE",
        "partition": "FROZEN_HOLDOUT", "data_kind": summary["data_kind"], "evidence_mode": evidence_mode,
        "evidence_scope": "SYNTHETIC_CONTRACT_ONLY" if summary["data_kind"] == "SYNTHETIC_FIXTURE"
            else "SOURCE_BACKED_DECLARATIONS_NOT_INDEPENDENT_GOLD",
        "training_manifest_sha256": expected_training_manifest_sha256,
        "calibration_manifest_sha256": expected_calibration_manifest_sha256,
        "scorer_summary_sha256": expected_scorer_summary_sha256, "model_binding": {k: summary[k]
            for k in bridge._MODEL_HASHES + bridge._MODEL_VALUES + bridge.semantic_model_fields(summary)},
        "policy_sha256": policy.policy_sha256, "artifact_sha256": artifact.artifact_sha256 if artifact else None,
        "expected_rows_sha256": canonical_sha256(expected), "observations_sha256": canonical_sha256(observed),
        "frozen_rows_sha256": canonical_sha256(graphs), "split_validation": validation,
        "counts": {"expected_rows": len(rows), "observed_rows": len(rows), "full_manifest_rows": len(manifest["rows"]),
            "source_terminals": dict(sorted(Counter(r["source_terminal"] for r in rows).items())),
            "truth_kinds": dict(sorted(Counter(r["truth_kind"] for r in rows).items())),
            "label_grades": dict(sorted(Counter(r["label_grade"] for r in rows).items())),
            "graph_rows": len(graphs), "calibration_bound_rows": len(shadows),
            "calibration_unavailable_rows": len(rows) - len(shadows),
            "shadow_actions": dict(sorted(Counter(r["action"] for r in rows).items()))},
        "rank_metrics": _rank_metrics(rows), "rows": rows, "calibration_evaluation": evaluated,
        "reason_codes": reasons, "formal_kpi_status": "NOT_ESTIMABLE", "quality_acceptance_claimed": False,
        "actual_quality_evaluated": False, "publication_authority": False, "public_apply": False,
        "central_db_write": False, "model_parameters_updated": False, "new_calibration_fit_executed": False,
        "thresholds_reselected": False, "source_truth_independently_verified": False}
    report["report_sha256"] = canonical_sha256(report)
    _require(len(raw_evaluation._bytes(report)) <= MAX_BYTES, "REPORT_BYTE_LIMIT")
    return report
