"""고정 learned raw score 평가와 CAL-only 임계값 선택. 확률 교정/공개 판정 아님.

공급 split의 provenance bytes는 검산하지만 annotation의 진실을 독립 증명하지
않는다. 데이터·모델 파일, 네트워크, optimizer를 호출하지 않는 순수 API다.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import re
from typing import Any

from ..grounding.reranker_training_split import validate_training_split
from ..grounding.candidate_reranker_shadow import _validate_view, DIGEST_SCOPE


SCHEMA = "candidate_reranker_score_evaluation_v1"
POLICY_SCHEMA = "candidate_reranker_threshold_policy_v1"
MAX_BYTES = 16 * 1024 * 1024
HASH_FIELDS = ("model_manifest_sha256", "model_sha256", "scorer_sha256",
               "feature_schema_sha256", "config_sha256", "training_split_manifest_sha256")
MODEL_FIELDS = HASH_FIELDS + ("backend", "data_kind", "training_status", "actual_model_available")
TERMINALS = frozenset({"SCORED_LEARNED", "NOT_SCORED_GENERATION_UNKNOWN",
    "NOT_SCORED_GENERATION_TRUNCATED", "NOT_SCORED_EMPTY_CORPUS", "EMPTY_CANDIDATE_SET",
    "EMPTY_QUERY", "UNAVAILABLE_MODEL", "INVALID_INPUT", "LIMIT_EXCEEDED", "ERROR", "NOT_AVAILABLE"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class RerankerEvaluationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RerankerEvaluationError(code)


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError) as exc:
        raise RerankerEvaluationError("JSON_INVALID") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _copy(value: Any) -> Any:
    raw = _bytes(value)
    _require(len(raw) <= MAX_BYTES, "EVALUATION_BYTE_LIMIT")
    return json.loads(raw)


def _hash(value: Any) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value))


def _number(value: Any) -> float:
    _require(type(value) in (int, float), "FINITE_NUMBER_REQUIRED")
    try:
        number = float(value)
    except OverflowError as exc:
        raise RerankerEvaluationError("FINITE_NUMBER_REQUIRED") from exc
    _require(math.isfinite(number), "FINITE_NUMBER_REQUIRED")
    return number


def _seal(value: dict, key: str = "report_sha256") -> dict:
    value[key] = canonical_sha256(value)
    return value


def _model(summary: Any, data_kind: str) -> dict:
    _require(type(summary) is dict and all(key in summary for key in MODEL_FIELDS), "MODEL_BINDING_MISSING")
    model = {key: summary[key] for key in MODEL_FIELDS}
    _require(all(_hash(model[key]) for key in HASH_FIELDS), "MODEL_SHA_INVALID")
    _require(model["backend"] == "PAIRWISE_LINEAR_V1"
             and model["training_status"] == "TRAINED_PAIRWISE_LINEAR"
             and model["actual_model_available"] is True, "LEARNED_MODEL_REQUIRED")
    _require(model["data_kind"] == data_kind and data_kind in {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"},
             "MODEL_DATA_KIND_MISMATCH")
    from ..grounding.candidate_reranker_event_bridge import semantic_model_fields
    model.update({key: summary[key] for key in semantic_model_fields(summary)})
    return model


def _id_mapping(row: dict, view: dict) -> dict:
    exposures = {item["candidate_id"]: item for item in row["exposures"]}
    bridges = {item["corpus_candidate_id"]: item for item in row["r2_id_bridges"]}
    mapping = {}
    for candidate in view["candidates"]:
        cid = candidate["candidate_id"]
        if view["candidate_namespace"] == "CORPUS_CANDIDATE":
            bridge = bridges.get(cid)
            _require(bridge is not None and bridge["status"] == "UNIQUE"
                     and len(bridge["candidate_ids"]) == 1, "EXPLICIT_UNIQUE_ID_BRIDGE_REQUIRED")
            mapped = bridge["candidate_ids"][0]
            _require(mapped in exposures and exposures[mapped]["corpus_candidate_id"] == cid,
                     "CORPUS_EXPOSURE_MISMATCH")
        else:
            mapped = cid
            _require(mapped in exposures, "CANDIDATE_EXPOSURE_MISSING")
        _require(mapped not in mapping.values(), "NON_UNIQUE_SCORE_ID_BRIDGE")
        mapping[cid] = mapped
    return mapping


def _capture(expected: dict, row: dict, view: dict, mapping: dict, payloads, evidence,
             *, semantic=False, split_manifest=None):
    # The shared learned source-span and strict JSON contracts contain no I/O.
    from ..grounding.candidate_reranker_learned import _span, _strict_capture, CAPTURE_SCHEMA
    bindings = expected["candidate_text_bindings"]
    candidates = view["candidates"]
    exposures = {item["candidate_id"]: item for item in row["exposures"]}
    _require(type(bindings) is list and len(bindings) == len(candidates), "CANDIDATE_TEXT_BINDING_COUNT")
    try:
        for candidate, bound in zip(candidates, bindings):
            _require(type(bound) is dict and set(bound) == {"candidate_id", "titles", "aliases"}
                     and bound["candidate_id"] == candidate["candidate_id"], "CANDIDATE_TEXT_ID_BINDING")
            for field in ("titles", "aliases"):
                _require(type(bound[field]) is list and len(bound[field]) == len(candidate[field]), "CANDIDATE_TEXT_COUNT")
                texts = [_span(span, payloads, exposures[mapping[candidate["candidate_id"]]]["source_ids"])["text"]
                         for span in bound[field]]
                _require(texts == candidate[field], "CANDIDATE_TEXT_SOURCE_MISMATCH")
        digest = expected["capture_sha256"]
        _require(_hash(digest) and digest in evidence and type(evidence[digest]) is bytes
                 and hashlib.sha256(evidence[digest]).hexdigest() == digest, "CAPTURE_BYTES_MISSING_OR_MISMATCH")
        label_hashes = {row["label_provenance"]["artifact_sha256"],
                       *(item["provenance"]["artifact_sha256"] for item in row["role_mentions"])}
        _require(digest not in label_hashes, "LABEL_AS_FEATURE_CAPTURE")
        capture = _strict_capture(evidence[digest])
    except ValueError as exc:
        raise RerankerEvaluationError(getattr(exc, "code", "CAPTURE_SOURCE_INVALID")) from exc
    assignment = row["assignment"]
    expected_capture = {"schema_version": CAPTURE_SCHEMA, "stage": "PRE_SELECTION",
        "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD", "example_id": assignment["example_id"],
        "post_id": assignment["post_id"], "binding": row["binding"],
        "source_spans_sha256": canonical_sha256(row["source_spans"]),
        "candidate_set_fingerprint": assignment["candidate_set_fingerprint"],
        "frozen_view_sha256": canonical_sha256(view),
        "candidate_text_bindings_sha256": canonical_sha256(bindings)}
    artifact = None
    if semantic:
        from ..grounding.candidate_reranker_semantic_input import CAPTURE_SCHEMA as SEMANTIC_CAPTURE_SCHEMA
        from ..grounding.candidate_reranker_event_bridge import resolve_example_semantic_input
        _require(_hash(capture.get("semantic_input_sha256")), "SEMANTIC_CAPTURE_EVIDENCE_REQUIRED")
        expected_capture.update(schema_version=SEMANTIC_CAPTURE_SCHEMA,
                                semantic_input_sha256=capture["semantic_input_sha256"])
        artifact = resolve_example_semantic_input(expected, row, payloads, evidence, split_manifest=split_manifest)
        _require(artifact is not None, "SEMANTIC_CAPTURE_REQUIRED")
    _require(capture == expected_capture, "PRESELECTION_CAPTURE_MISMATCH")
    return artifact


def _observation(expected: dict, observation: dict, row: dict, model: dict, payloads, evidence,
                 *, split_manifest=None) -> dict:
    _require(type(expected) is dict and set(expected) == {"example_id", "publication_scope_id", "frozen_view",
                                                         "candidate_text_bindings", "capture_sha256"},
             "EXPECTED_ROW_SCHEMA")
    _require(type(expected["publication_scope_id"]) is str and bool(expected["publication_scope_id"].strip()),
             "EXPECTED_SCOPE_REQUIRED")
    _require(type(observation) is dict and set(observation) == {"example_id", "receipt"}, "OBSERVATION_SCHEMA")
    assignment = row["assignment"]
    _require(expected["example_id"] == observation["example_id"] == assignment["example_id"], "EXAMPLE_BINDING")
    try:
        view = _validate_view(_copy(expected["frozen_view"]))
    except ValueError as exc:
        raise RerankerEvaluationError("INVALID_FROZEN_VIEW") from exc
    _require(type(view["post_id"]) is type(assignment["post_id"])
             and view["post_id"] == assignment["post_id"], "SOURCE_POST_BINDING")
    span_text = [(span["raw_path"], span["text"]) for span in row["source_spans"]]
    _require([(part["raw_path"], part["text"]) for part in view["source_view"]["fragments"]] == span_text,
             "SOURCE_FRAGMENT_ORDER_OR_COVERAGE_MISMATCH")
    if view["candidate_namespace"] == "CANDIDATE_OPTION":
        _require(view["candidate_set_fingerprint"] == assignment["candidate_set_fingerprint"], "CANDIDATE_SET_BINDING")
    mapping = _id_mapping(row, view)
    from ..grounding.candidate_reranker_event_bridge import semantic_model_fields, validate_semantic_receipt
    semantic_fields = semantic_model_fields(model)
    artifact = _capture(expected, row, view, mapping, payloads, evidence,
        semantic=bool(semantic_fields), split_manifest=split_manifest)
    receipt = observation["receipt"]
    _require(type(receipt) is dict and len(_bytes(receipt)) <= 64 * 1024, "RECEIPT_SIZE_OR_TYPE")
    _require(receipt.get("schema_version") == "candidate_reranker_shadow_v1"
             and receipt.get("mode") == "SHADOW" and receipt.get("receipt_digest_scope") == DIGEST_SCOPE,
             "RECEIPT_SCHEMA")
    _require(type(receipt.get("status")) is str and receipt["status"] in TERMINALS, "TERMINAL_INVALID")
    scored = receipt["status"] == "SCORED_LEARNED"
    _require(receipt.get("receipt_sha256") == canonical_sha256({key: value for key, value in receipt.items()
             if key not in {"latency_ms", "receipt_sha256", "binding"}}), "RECEIPT_SHA_MISMATCH")
    # 미가용 모델은 아직 새 모델을 읽지 않았으므로 v2 소비를 주장할 수 없다.
    # NIL evaluator는 이 경로를 원본 unavailable adapter template과 먼저 대조한다.
    if semantic_fields and receipt.get("actual_model_available") is False:
        _require(not any(key in receipt for key in (*semantic_fields, "semantic_consumption", "semantic_input_sha256")),
                 "UNAVAILABLE_SEMANTIC_CONSUMPTION_CONTRADICTION")
    else:
        validate_semantic_receipt(receipt, view, model, artifact)
    _require(type(receipt.get("post_id")) is type(assignment["post_id"])
             and receipt["post_id"] == assignment["post_id"], "RECEIPT_POST_BINDING")
    binding = {**row["binding"], "post_id": assignment["post_id"],
               "publication_scope_id": expected["publication_scope_id"], "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    _require(_bytes(receipt.get("binding")) == _bytes(binding), "RECEIPT_STORAGE_BINDING")
    _require(all(receipt.get(key) is False for key in ("publication_authority", "public_apply", "central_db_write")),
             "RECEIPT_AUTHORITY")
    _require(receipt.get("probability_status") == "NOT_AVAILABLE_UNCALIBRATED"
             and receipt.get("selected_candidate_id") is None and receipt.get("nil_probability") is None
             and receipt.get("operational_effect") == "NONE_SHADOW_ONLY", "RAW_SCORE_NOT_PROBABILITY_OR_DECISION")
    limits = []
    _require(receipt.get("model_manifest_sha256") == model["model_manifest_sha256"], "MODEL_MANIFEST_BINDING")
    for key in HASH_FIELDS:
        observed = receipt.get(key)
        if observed is None and not scored:
            limits.append("MISSING_" + key.upper())
        else:
            _require(observed == model[key], "MODEL_FINGERPRINT_MISMATCH")
    if scored:
        _require(all(type(receipt.get(key)) is type(model[key]) and receipt.get(key) == model[key]
                     for key in MODEL_FIELDS), "LEARNED_RECEIPT_MODEL_BINDING")
    else:
        for key in ("backend", "data_kind"):
            if receipt.get(key) not in (None, "UNAVAILABLE"):
                _require(receipt[key] == model[key], "UNAVAILABLE_MODEL_IDENTITY_CONTRADICTION")
    fingerprints = {"query_sha256": canonical_sha256(view["source_view"]),
        "input_sha256": canonical_sha256(view), "candidate_view_sha256": canonical_sha256(view["candidates"]),
        "generation_sha256": view["generation_sha256"],
        "candidate_set_fingerprint": view["candidate_set_fingerprint"],
        "candidate_namespace": view["candidate_namespace"], "generation_status": view["generation_status"]}
    for key, value in fingerprints.items():
        observed = receipt.get(key)
        if value is None:
            _require(observed is None, "OBSERVATION_SOURCE_BINDING")
        elif observed is None and not scored:
            limits.append("MISSING_" + key.upper())
        else:
            _require(type(observed) is type(value) and observed == value, "OBSERVATION_SOURCE_BINDING")
    ids = [item["candidate_id"] for item in view["candidates"]]
    ranked = receipt.get("ranked_candidates")
    _require(type(ranked) is list, "RANKING_REQUIRED")
    if scored:
        _require(view["generation_status"] == "COMPLETE" and bool(ids)
                 and receipt.get("frozen_candidate_ids") == ids, "SCORED_FROZEN_IDS")
        _require(len(ranked) == len(ids), "SCORE_COUNT_MISMATCH")
        for item in ranked:
            _require(type(item) is dict and set(item) == {"candidate_id", "score"}
                     and type(item["candidate_id"]) is str, "SCORE_ROW_SCHEMA")
            _number(item["score"])
        _require(sorted(item["candidate_id"] for item in ranked) == sorted(ids), "SCORE_ID_SET_MISMATCH")
        _require(ranked == sorted(ranked, key=lambda item: (-item["score"], item["candidate_id"])), "SCORE_ORDER_MISMATCH")
        _require(receipt.get("candidate_observations") == [{"candidate_id": candidate["candidate_id"],
                 "role_observations": candidate["role_observations"]} for candidate in view["candidates"]],
                 "SCORE_ROLE_OBSERVATION_MISMATCH")
    else:
        _require(not ranked, "UNAVAILABLE_WITH_RANKING")
        if receipt.get("frozen_candidate_ids") not in (None, []):
            _require(receipt["frozen_candidate_ids"] == ids, "UNAVAILABLE_FROZEN_ID_CONTRADICTION")
        if receipt["status"] == "EMPTY_CANDIDATE_SET":
            _require(not ids and view["generation_status"] == "COMPLETE", "FALSE_EMPTY_CANDIDATES")
        if receipt["status"] in {"NOT_SCORED_GENERATION_UNKNOWN", "NOT_SCORED_GENERATION_TRUNCATED"}:
            _require(receipt["status"] == "NOT_SCORED_GENERATION_" + view["generation_status"],
                     "FALSE_GENERATION_TERMINAL")
        if receipt["status"] == "EMPTY_QUERY":
            _require(not any(part["text"].strip() for part in view["source_view"]["fragments"]), "FALSE_EMPTY_QUERY")
    score_ids = [mapping[item["candidate_id"]] for item in ranked]
    margin = _number(ranked[0]["score"] - ranked[1]["score"]) if len(ranked) > 1 else None
    truth = assignment["truth_label"]
    gold_present = (truth in mapping.values()) if assignment["truth_kind"] == "CANDIDATE" and view["generation_status"] == "COMPLETE" else None
    return {"example_id": assignment["example_id"], "post_id": assignment["post_id"],
        "truth_kind": assignment["truth_kind"], "truth_label": truth,
        "label_grade": row["label_provenance"]["grade"],
        "label_provenance_sha256": assignment["label_provenance_sha256"],
        "source_terminal": receipt["status"], "generation_status": view["generation_status"], "binding_limits": limits,
        "receipt_sha256": receipt["receipt_sha256"], "gold_present": gold_present,
        "ranked_candidate_ids": score_ids, "top_score": ranked[0]["score"] if ranked else None,
        "margin": margin, "scored": scored,
        "reciprocal_rank": (1.0 / (score_ids.index(truth) + 1) if truth in score_ids else 0.0)
                           if scored and assignment["truth_kind"] == "CANDIDATE" else None}


def _prepare(*, split_manifest, source_payloads, evidence_payloads, expected_rows,
             observations, scorer_summary, partition: str) -> dict:
    manifest, expected, observed, summary = map(_copy, (split_manifest, expected_rows, observations, scorer_summary))
    validation = validate_training_split(manifest, source_payloads=source_payloads, evidence_payloads=evidence_payloads)
    _require(validation["status"] != "INVALID", "TRAINING_SPLIT_INVALID")
    model = _model(summary, manifest["data_kind"])
    _require(model["training_split_manifest_sha256"] == manifest["manifest_sha256"],
             "MODEL_TRAINING_SPLIT_MISMATCH")
    rows = [row for row in manifest["rows"] if row["assignment"]["split"] == partition]
    _require(type(expected) is list and type(observed) is list and bool(rows), "EXPECTED_UNIVERSE_REQUIRED")
    ids = [row["assignment"]["example_id"] for row in rows]
    _require([item.get("example_id") if type(item) is dict else None for item in expected] == ids,
             "EXPECTED_UNIVERSE_ORDER_OR_SET_MISMATCH")
    _require([item.get("example_id") if type(item) is dict else None for item in observed] == ids,
             "OBSERVATION_UNIVERSE_ORDER_OR_SET_MISMATCH")
    results = [_observation(exp, obs, row, model, source_payloads, evidence_payloads, split_manifest=manifest)
               for exp, obs, row in zip(expected, observed, rows)]
    return {"manifest": manifest, "validation": validation, "model": model, "rows": results,
        "partition": partition, "expected_sha256": canonical_sha256(expected),
        "observations_sha256": canonical_sha256(observed)}


def _decide(rows: list[dict], score_threshold: float, margin_threshold: float) -> list[dict]:
    decisions = []
    for source in rows:
        row = deepcopy(source)
        chosen = None
        if row["scored"]:
            action = "ABSTAIN"
            reason = "SINGLE_CANDIDATE_MARGIN_UNAVAILABLE" if row["margin"] is None else "RAW_SCORE_THRESHOLD"
            if row["margin"] is not None and row["top_score"] >= score_threshold and row["margin"] >= margin_threshold:
                action, reason = "SELECT_CANDIDATE", "RAW_SCORE_AND_MARGIN_THRESHOLD_MET"
                chosen = row["ranked_candidate_ids"][0]
        elif row["source_terminal"] == "EMPTY_CANDIDATE_SET":
            action, reason = "ABSTAIN", "EMPTY_CANDIDATE_SET_NOT_NIL"
        else:
            action, reason = "UNAVAILABLE", row["source_terminal"]
        row.update(action=action, action_reason=reason, selected_candidate_id=chosen,
                   correct=(chosen == row["truth_label"]) if chosen is not None else None)
        decisions.append(row)
    return decisions


def _metric(numerator, denominator, *, status="DESCRIPTIVE_RAW_SCORE") -> dict:
    return {"value": numerator / denominator if denominator else None,
            "numerator": numerator, "denominator": denominator,
            "status": status if denominator else "NOT_ESTIMABLE_EMPTY_DENOMINATOR"}


def _metrics(rows: list[dict]) -> dict:
    total = len(rows)
    work = [row for row in rows if row["truth_kind"] == "CANDIDATE"]
    rankable = [row for row in work if row["scored"]]
    present = [row for row in work if row["gold_present"]]
    generation_observed = [row for row in work if row["gold_present"] is not None]
    present_scored = [row for row in present if row["scored"]]
    selected = [row for row in rows if row["action"] == "SELECT_CANDIDATE"]
    gold_top = sum(row["ranked_candidate_ids"][0] == row["truth_label"] for row in present_scored)
    gold_selected = sum(row["correct"] is True for row in present)
    return {"mrr_scored_work": _metric(sum(row["reciprocal_rank"] for row in rankable), len(rankable)),
        "mrr_all_work_operational": _metric(sum(row["reciprocal_rank"] for row in rankable), len(work), status="ACCOUNTING_ONLY_UNAVAILABLE_AS_ZERO"),
        "candidate_recall": _metric(sum(row["gold_present"] is True for row in generation_observed), len(generation_observed), status="COMPLETE_FROZEN_CANDIDATE_SET_ONLY"),
        "candidate_recall_operational": _metric(sum(row["gold_present"] is True for row in work), len(work), status="ACCOUNTING_ONLY_UNKNOWN_AS_MISS"),
        "gold_present_top1_accuracy": _metric(gold_top, len(present_scored)),
        "gold_present_selection_accuracy": _metric(gold_selected, len(present), status="OPERATIONAL_GOLD_PRESENT_INCLUDING_ALL_TERMINALS"),
        "score_coverage": _metric(sum(row["scored"] for row in rows), total),
        "decision_coverage": _metric(len(selected), total),
        "selective_risk": _metric(sum(row["correct"] is False for row in selected), len(selected)),
        "operational_accuracy": _metric(sum(row["correct"] is True for row in rows), total, status="ACCOUNTING_ONLY_ALL_TERMINALS"),
        "nil": {"policy_status": "UNSUPPORTED_NO_VALIDATED_NIL_POLICY", "predicted_nil": 0,
            "truth_count": sum(row["truth_kind"] == "NIL" for row in rows),
            "candidate_selected_on_nil_truth": sum(row["truth_kind"] == "NIL" for row in selected),
            "precision": None, "recall": None},
        "probability_status": "NOT_AVAILABLE_UNCALIBRATED"}


def _base(context: dict) -> dict:
    rows, validation = context["rows"], context["validation"]
    return {"schema_version": SCHEMA, "partition": context["partition"],
        "split_manifest_sha256": context["manifest"]["manifest_sha256"],
        "split_validation_sha256": validation["report_sha256"], "split_status": validation["status"],
        "split_issues": validation["issues"], "model_binding": context["model"],
        "model_binding_sha256": canonical_sha256(context["model"]),
        "expected_rows_sha256": context["expected_sha256"], "observations_sha256": context["observations_sha256"],
        "data_kind": context["manifest"]["data_kind"],
        "evidence_scope": "SYNTHETIC_ONLY" if context["manifest"]["data_kind"] == "SYNTHETIC_FIXTURE"
                          else "SOURCE_BACKED_DECLARATIONS_NOT_INDEPENDENT_GOLD",
        "counts": {"full_manifest_rows": len(context["manifest"]["rows"]), "expected_rows": len(rows),
            "observed_rows": len(rows), "unique_posts": len({row["post_id"] for row in rows}),
            "source_terminals": {status: sum(row["source_terminal"] == status for row in rows) for status in sorted(TERMINALS)},
            "truth_kinds": dict(sorted(Counter(row["truth_kind"] for row in rows).items())),
            "label_grades": dict(sorted(Counter(row["label_grade"] for row in rows).items()))},
        "publication_authority": False, "public_apply": False, "central_db_write": False,
        "probability_status": "NOT_AVAILABLE_UNCALIBRATED", "nil_policy_status": "UNSUPPORTED",
        "formal_kpi_status": "NOT_ESTIMABLE", "quality_acceptance_claimed": False}


def fit_calibration_thresholds(*, split_manifest, source_payloads, evidence_payloads,
        expected_rows, observations, scorer_summary, score_thresholds, margin_thresholds,
        max_empirical_risk, minimum_coverage=0.0) -> dict:
    context = _prepare(split_manifest=split_manifest, source_payloads=source_payloads,
        evidence_payloads=evidence_payloads, expected_rows=expected_rows, observations=observations,
        scorer_summary=scorer_summary, partition="CALIBRATION")
    maximum, minimum = _number(max_empirical_risk), _number(minimum_coverage)
    _require(0 <= maximum <= 1 and 0 <= minimum <= 1, "POLICY_RISK_OR_COVERAGE_RANGE")
    _require(type(score_thresholds) is list and type(margin_thresholds) is list
             and 0 < len(score_thresholds) <= 32 and 0 < len(margin_thresholds) <= 32
             and len(score_thresholds) * len(margin_thresholds) <= 256, "POLICY_GRID_LIMIT")
    scores = sorted({_number(value) for value in score_thresholds})
    margins = sorted({_number(value) for value in margin_thresholds})
    _require(min(margins) >= 0, "NEGATIVE_MARGIN_THRESHOLD")
    report = _base(context)
    if context["validation"]["status"] != "VALID":
        return _seal({**report, "status": "NOT_ESTIMABLE_SPLIT_NOT_READY", "metrics": None,
                      "rows": context["rows"], "policy": None})
    candidates = []
    for score in scores:
        for margin in margins:
            metrics = _metrics(_decide(context["rows"], score, margin))
            risk, coverage = metrics["selective_risk"]["value"], metrics["decision_coverage"]["value"]
            if risk is not None and risk <= maximum and coverage >= minimum:
                candidates.append((coverage, risk, score, margin))
    if not candidates:
        return _seal({**report, "status": "NO_FEASIBLE_POLICY", "metrics": None,
                      "rows": context["rows"], "policy": None})
    _, _, score, margin = min(candidates, key=lambda item: (-item[0], item[1], item[2], item[3]))
    decisions = _decide(context["rows"], score, margin)
    metrics = _metrics(decisions)
    report["counts"]["actions"] = dict(sorted(Counter(row["action"] for row in decisions).items()))
    policy = _seal({"schema_version": POLICY_SCHEMA, "method": "CAL_ONLY_RAW_SCORE_MARGIN_V1",
        "split_manifest_sha256": report["split_manifest_sha256"],
        "model_binding_sha256": report["model_binding_sha256"], "data_kind": report["data_kind"],
        "cal_expected_rows_sha256": context["expected_sha256"], "cal_observations_sha256": context["observations_sha256"],
        "score_thresholds": scores, "margin_thresholds": margins,
        "max_empirical_risk": maximum, "minimum_coverage": minimum,
        "score_threshold": score, "margin_threshold": margin,
        "cal_decision_coverage": metrics["decision_coverage"], "cal_selective_risk": metrics["selective_risk"],
        "tie_break": "MAX_COVERAGE_MIN_RISK_SCORE_ASC_MARGIN_ASC",
        "single_candidate": "ABSTAIN_MARGIN_UNAVAILABLE", "nil_policy": "UNSUPPORTED_ABSTAIN_ONLY",
        "probability_status": "NOT_AVAILABLE_UNCALIBRATED", "publication_authority": False}, "policy_sha256")
    return _seal({**report, "status": "CAL_POLICY_FROZEN", "metrics": metrics,
                  "rows": decisions, "policy": policy})


def evaluate_frozen_scores(*, split_manifest, source_payloads, evidence_payloads,
        expected_rows, observations, scorer_summary, threshold_policy, expected_policy_sha256) -> dict:
    context = _prepare(split_manifest=split_manifest, source_payloads=source_payloads,
        evidence_payloads=evidence_payloads, expected_rows=expected_rows, observations=observations,
        scorer_summary=scorer_summary, partition="FROZEN_HOLDOUT")
    report = _base(context)
    policy = _copy(threshold_policy)
    _require(type(policy) is dict and _hash(expected_policy_sha256), "PINNED_POLICY_REQUIRED")
    body = {key: value for key, value in policy.items() if key != "policy_sha256"}
    _require(policy.get("policy_sha256") == expected_policy_sha256 == canonical_sha256(body), "POLICY_SHA_MISMATCH")
    _require(policy.get("schema_version") == POLICY_SCHEMA and policy.get("method") == "CAL_ONLY_RAW_SCORE_MARGIN_V1"
             and policy.get("split_manifest_sha256") == report["split_manifest_sha256"]
             and policy.get("model_binding_sha256") == report["model_binding_sha256"]
             and policy.get("data_kind") == report["data_kind"], "POLICY_MODEL_OR_SPLIT_BINDING")
    _require(policy.get("nil_policy") == "UNSUPPORTED_ABSTAIN_ONLY"
             and policy.get("single_candidate") == "ABSTAIN_MARGIN_UNAVAILABLE"
             and policy.get("publication_authority") is False
             and policy.get("probability_status") == "NOT_AVAILABLE_UNCALIBRATED", "POLICY_SEMANTICS")
    score, margin = _number(policy.get("score_threshold")), _number(policy.get("margin_threshold"))
    _require(margin >= 0 and score in policy.get("score_thresholds", [])
             and margin in policy.get("margin_thresholds", [])
             and _hash(policy.get("cal_expected_rows_sha256")) and _hash(policy.get("cal_observations_sha256")),
             "POLICY_CAL_BINDING")
    if context["validation"]["status"] != "VALID":
        return _seal({**report, "status": "NOT_ESTIMABLE_SPLIT_NOT_READY", "metrics": None,
                      "rows": context["rows"], "policy_sha256": expected_policy_sha256})
    decisions = _decide(context["rows"], score, margin)
    report["counts"]["actions"] = dict(sorted(Counter(row["action"] for row in decisions).items()))
    return _seal({**report, "status": "FROZEN_SCORE_EVALUATED", "metrics": _metrics(decisions),
                  "rows": decisions, "policy_sha256": expected_policy_sha256,
                  "thresholds_refit_on_frozen": False})
