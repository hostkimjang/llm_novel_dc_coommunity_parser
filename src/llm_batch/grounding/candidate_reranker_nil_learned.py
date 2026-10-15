"""Frozen pairwise candidate scores plus a TRAIN-only linear NIL logit.

API: train_model(split_manifest, *, source_payloads, evidence_payloads, examples,
config={"base": {...}, "nil_head": {...}}) trains the base then the NIL head.
train_nil_head(base_model, split_manifest, *, source_payloads,
evidence_payloads, examples, config=None) -> {model, training_report};
validate_model(model) -> JSON deepcopy; score_event_logits(model, frozen_view)
-> {labels, raw_scores, ...}. Labels preserve input candidate order, then NIL.
No probabilities, selected label, calibration, filesystem, or external calls.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import math

from . import candidate_reranker_learned as pairwise
from .reranker_training_split import validate_training_split

BACKEND = "NIL_AUGMENTED_LINEAR_V1"
MODEL_SCHEMA = "candidate_reranker_nil_learned_model_v1"
FEATURE_SCHEMA = "candidate_reranker_nil_features_v1"
REPORT_SCHEMA = "candidate_reranker_nil_training_report_v1"
EVENT_SCHEMA = "candidate_reranker_nil_event_logits_v1"
MODEL_SCHEMA_V2 = "candidate_reranker_nil_learned_model_v2"
FEATURE_SCHEMA_V2 = "candidate_reranker_nil_features_v2"
REPORT_SCHEMA_V2 = "candidate_reranker_nil_training_report_v2"
NIL_LABEL = "__NIL__"
PROBABILITY_STATUS = "NOT_AVAILABLE_UNCALIBRATED"
DEFAULT_CONFIG = {"epochs": 80, "learning_rate": 0.2, "l2": 0.01}
FEATURE_NAMES = ("bias", "candidate_count_fraction", *(
    f"{aggregation}_{name}" for aggregation in ("max", "mean") for name in pairwise.FEATURE_NAMES))
MAX_MODEL_BYTES = 128 * 1024
MAX_TRAIN_EXAMPLES = 256
MAX_OPTIMIZATION_STEPS = 51200
MAX_WEIGHT = 100.0
NILLearnedRerankerError = pairwise.LearnedRerankerError
canonical_sha256 = pairwise.canonical_sha256
_require = pairwise._require
_object = pairwise._object
_copy_json = pairwise._copy_json
_number = pairwise._number
_hash = pairwise._hash
_BINDING_FIELDS = {
    "split_manifest_sha256", "split_validation_sha256", "train_examples_sha256",
    "train_rows_sha256", "source_payloads_sha256", "evidence_payloads_sha256",
    "base_model_sha256", "label_grade_counts", "train_example_count", "truth_counts",
    "optimization_steps", "preselection_authority", "exposure_completeness",
}


def _contract(feature_schema=FEATURE_SCHEMA):
    _require(feature_schema in (FEATURE_SCHEMA, FEATURE_SCHEMA_V2), "FEATURE_SCHEMA_UNSUPPORTED")
    return {"schema_version": feature_schema, "stage": "PRE_SELECTION",
        "feature_names": list(FEATURE_NAMES), "base_features": pairwise._contract(
            pairwise.FEATURE_SCHEMA_V2 if feature_schema == FEATURE_SCHEMA_V2 else pairwise.FEATURE_SCHEMA),
        "aggregation": "PER_FEATURE_MAX_AND_MEAN_OVER_FROZEN_CANDIDATES",
        "candidate_count_divisor": 20, "bias": 1,
        "candidate_score_policy": "FROZEN_BASE_MODEL_NO_UPDATES",
        "loss": "MEAN_CANDIDATE_PLUS_NIL_SOFTMAX_NLL_PLUS_L2_ALL_NIL_WEIGHTS",
        "optimizer": "DETERMINISTIC_FULL_BATCH_GRADIENT_DESCENT_ZERO_INITIALIZATION",
        "empty_candidates": "REJECT_NOT_NIL", "single_candidate": "CANDIDATE_PLUS_NIL_RAW_LOGITS",
        "eligible_candidates": "COMPLETE_WORK_CANDIDATES_ONLY",
        "labels": "INPUT_CANDIDATE_ORDER_THEN_RESERVED_NIL",
        "excluded": ["candidate_id", "gold_label", "final_selection", "label_role_annotations", "predictions"],
        "probability_status": PROBABILITY_STATUS, "publication_authority": False}


FEATURE_CONTRACT = _contract()


def _config(config):
    # The established finite, strict epoch/rate/L2 policy is reused unchanged.
    return pairwise._config(config)


def _event_view(value):
    view = pairwise._view(value)
    _require(all(c["option_kind"] == "WORK_CANDIDATE" and c["event_eligible"] is True
                 and c["identity_conflict"] is False for c in view["candidates"]),
             "NIL_EVENT_CANDIDATE_INELIGIBLE")
    return view


def _feature_vector(view):
    matrix = pairwise._features(view)
    size = len(matrix)
    _require(1 <= size <= 20, "EMPTY_OR_OVERSIZED_CANDIDATES")
    columns = tuple(zip(*matrix))
    vector = (1.0, size / 20.0, *(max(col) for col in columns),
              *(math.fsum(sorted(col)) / size for col in columns))
    _require(len(vector) == len(FEATURE_NAMES)
             and all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in vector), "NIL_FEATURE_INVALID")
    return vector


def _candidate_scores(base_model, view, *, semantic_input=None, evidence_payloads=None):
    # Directly use the established scorer, then restore the frozen input order.
    scored = pairwise.score_view(base_model, view, semantic_input=semantic_input, evidence_payloads=evidence_payloads)
    table = {row["candidate_id"]: row["score"] for row in scored}
    ids = [c["candidate_id"] for c in view["candidates"]]
    _require(len(scored) == len(table) == len(ids) and set(table) == set(ids), "BASE_SCORE_IDS_INVALID")
    values = tuple(table[cid] for cid in ids)
    _require(all(type(v) in (int, float) and math.isfinite(v) for v in values), "SCORE_NONFINITE")
    return values


def _distribution(candidate_scores, nil_score):
    """Stable log partition and optimizer-only NIL mass; never exported."""
    high = max(*candidate_scores, nil_score)
    mass = math.exp(nil_score - high)
    total = math.fsum([*(math.exp(score - high) for score in candidate_scores), mass])
    return high + math.log(total), mass / total


def _loss(weights, rows, l2):
    values = []
    for vector, candidates, target in rows:
        nil_score = pairwise._dot(weights, vector)
        partition, _ = _distribution(candidates, nil_score)
        values.append(partition - (nil_score if target == len(candidates) else candidates[target]))
    return math.fsum(values) / len(values) + l2 * pairwise._dot(weights, weights) / 2


def validate_model(model):
    model = _copy_json(model, MAX_MODEL_BYTES)
    _object(model, {"schema_version", "backend", "feature_schema", "data_kind", "feature_contract",
        "feature_contract_sha256", "base_model", "base_model_sha256", "config", "config_sha256",
        "weights", "weights_sha256", "training_binding", "publication_authority", "probability_status",
        "actual_performance_evaluated", "model_sha256"})
    semantic = model["schema_version"] == MODEL_SCHEMA_V2
    feature_schema = FEATURE_SCHEMA_V2 if semantic else FEATURE_SCHEMA
    _require(model["schema_version"] == (MODEL_SCHEMA_V2 if semantic else MODEL_SCHEMA)
             and model["backend"] == BACKEND and model["feature_schema"] == feature_schema, "MODEL_VERSION_INVALID")
    contract = _contract(feature_schema)
    base = pairwise.validate_model(model["base_model"])
    _require(base["feature_schema"] == (pairwise.FEATURE_SCHEMA_V2 if semantic else pairwise.FEATURE_SCHEMA),
             "BASE_FEATURE_SCHEMA_MISMATCH")
    _require(model["base_model_sha256"] == canonical_sha256(base), "BASE_MODEL_SHA_MISMATCH")
    _require(model["data_kind"] == base["data_kind"], "BASE_DATA_KIND_MISMATCH")
    _require(pairwise._bytes(model["feature_contract"]) == pairwise._bytes(contract)
             and model["feature_contract_sha256"] == canonical_sha256(contract), "FEATURE_CONTRACT_INVALID")
    _object(model["config"], DEFAULT_CONFIG, "CONFIG_INVALID")
    _require(model["config"] == _config(model["config"])
             and model["config_sha256"] == canonical_sha256(model["config"]), "CONFIG_INVALID")
    weights = model["weights"]
    _require(type(weights) is list and len(weights) == len(FEATURE_NAMES), "WEIGHTS_INVALID")
    for weight in weights:
        _number(weight, -MAX_WEIGHT, MAX_WEIGHT)
    _require(model["weights_sha256"] == canonical_sha256(weights), "WEIGHTS_SHA_MISMATCH")
    semantic_fields = {"semantic_feature_contract_sha256", "semantic_inputs_sha256"} if semantic else set()
    binding = _object(model["training_binding"], _BINDING_FIELDS | semantic_fields)
    for field in _BINDING_FIELDS | semantic_fields:
        if field.endswith("sha256"):
            _hash(binding[field])
    _require(binding["base_model_sha256"] == model["base_model_sha256"], "BASE_MODEL_SHA_MISMATCH")
    count = binding["train_example_count"]
    _require(type(count) is int and 2 <= count <= MAX_TRAIN_EXAMPLES, "TRAIN_EXAMPLE_LIMIT")
    truths = _object(binding["truth_counts"], {"CANDIDATE", "NIL"}, "TRUTH_COUNTS_INVALID")
    _require(all(type(v) is int and v > 0 for v in truths.values()) and sum(truths.values()) == count,
             "BOTH_TRAIN_TRUTH_CLASSES_REQUIRED")
    _require(type(binding["optimization_steps"]) is int and
             binding["optimization_steps"] == count * model["config"]["epochs"] <= MAX_OPTIMIZATION_STEPS,
             "OPTIMIZATION_BUDGET_INVALID")
    # Identical TRAIN captures and declared data are required, not merely a name
    # for the split. The base remains byte-identical throughout NIL fitting.
    for field in ("split_manifest_sha256", "split_validation_sha256", "train_examples_sha256",
                  "train_rows_sha256", "source_payloads_sha256", "evidence_payloads_sha256",
                  "label_grade_counts", "train_example_count", "preselection_authority", "exposure_completeness"):
        _require(pairwise._bytes(binding[field]) == pairwise._bytes(base["training_binding"][field]),
                 "BASE_TRAINING_BINDING_MISMATCH", field)
    for field in semantic_fields:
        _require(binding[field] == base["training_binding"][field], "BASE_SEMANTIC_BINDING_MISMATCH", field)
    _require(model["publication_authority"] is False and model["actual_performance_evaluated"] is False
             and model["probability_status"] == PROBABILITY_STATUS, "AUTHORITY_INVALID")
    _require(_hash(model["model_sha256"]) == canonical_sha256({k: v for k, v in model.items() if k != "model_sha256"}),
             "MODEL_SHA_MISMATCH")
    return model


def score_event_logits(model, frozen_view, *, semantic_input=None, evidence_payloads=None):
    model, view = validate_model(model), _event_view(frozen_view)
    vector = _feature_vector(view)
    candidates = _candidate_scores(model["base_model"], view, semantic_input=semantic_input, evidence_payloads=evidence_payloads)
    nil_score = pairwise._dot(model["weights"], vector)
    _require(math.isfinite(nil_score), "SCORE_NONFINITE")
    return {"schema_version": EVENT_SCHEMA, "backend": BACKEND, "data_kind": model["data_kind"],
        "candidate_scores": [{"candidate_id": c["candidate_id"], "score": score}
                             for c, score in zip(view["candidates"], candidates)], "nil_score": nil_score,
        "labels": [c["candidate_id"] for c in view["candidates"]] + [NIL_LABEL],
        "raw_scores": [*candidates, nil_score], "candidate_namespace": view["candidate_namespace"],
        "model_sha256": canonical_sha256(model), "base_model_sha256": model["base_model_sha256"],
        "training_split_manifest_sha256": model["training_binding"]["split_manifest_sha256"],
        "input_sha256": canonical_sha256(view), "feature_sha256": canonical_sha256(vector),
        "probability_status": PROBABILITY_STATUS, "nil_probability": None, "selected_label": None,
        "publication_authority": False, "public_apply": False, "central_db_write": False}


def train_nil_head(base_model, split_manifest, *, source_payloads, evidence_payloads, examples, config=None,
                   feature_schema=FEATURE_SCHEMA):
    base = pairwise.validate_model(base_model)
    _require(feature_schema in (FEATURE_SCHEMA, FEATURE_SCHEMA_V2), "FEATURE_SCHEMA_UNSUPPORTED")
    semantic = feature_schema == FEATURE_SCHEMA_V2
    base_feature_schema = pairwise.FEATURE_SCHEMA_V2 if semantic else pairwise.FEATURE_SCHEMA
    _require(base["feature_schema"] == base_feature_schema, "BASE_FEATURE_SCHEMA_MISMATCH")
    contract = _contract(feature_schema)
    manifest, examples = _copy_json(split_manifest), _copy_json(examples)
    payloads, evidence, config = pairwise._payloads(source_payloads), pairwise._payloads(evidence_payloads), _config(config)
    _require(sum(map(len, payloads.values())) + sum(map(len, evidence.values())) <= pairwise.MAX_DATA_BYTES,
             "PAYLOAD_BYTE_LIMIT")
    validation = validate_training_split(manifest, source_payloads=payloads, evidence_payloads=evidence)
    _require(validation["status"] == "VALID", "FULL_SPLIT_NOT_VALID")
    _require(base["training_binding"]["split_manifest_sha256"] == manifest["manifest_sha256"],
             "BASE_SPLIT_MISMATCH")
    _require(base["data_kind"] == manifest["data_kind"], "BASE_DATA_KIND_MISMATCH")
    train_rows = sorted((r for r in manifest["rows"] if r["assignment"]["split"] == "TRAIN"),
                        key=lambda r: r["assignment"]["example_id"])
    _require(2 <= len(train_rows) <= MAX_TRAIN_EXAMPLES, "BOTH_TRAIN_TRUTH_CLASSES_REQUIRED")
    _require(type(examples) is list and len(examples) == len(train_rows), "TRAIN_EXAMPLE_SET_MISMATCH")
    for example in examples:
        _object(example, {"example_id", "frozen_view", "candidate_text_bindings", "capture_sha256"}, "EXAMPLE_SCHEMA_INVALID")
        _require(type(example["example_id"]) is str, "EXAMPLE_ID_INVALID")
    by_id = {example["example_id"]: example for example in examples}
    _require(len(by_id) == len(examples) and set(by_id) == {r["assignment"]["example_id"] for r in train_rows},
             "TRAIN_EXAMPLE_SET_MISMATCH")
    truth_counts = Counter(r["assignment"]["truth_kind"] for r in train_rows)
    _require(set(truth_counts) == {"CANDIDATE", "NIL"}, "BOTH_TRAIN_TRUTH_CLASSES_REQUIRED")
    binding = {"split_manifest_sha256": manifest["manifest_sha256"], "split_validation_sha256": validation["report_sha256"],
        "train_examples_sha256": canonical_sha256([by_id[r["assignment"]["example_id"]] for r in train_rows]),
        "train_rows_sha256": canonical_sha256(train_rows),
        "source_payloads_sha256": canonical_sha256({sid: hashlib.sha256(raw).hexdigest() for sid, raw in payloads.items()}),
        "evidence_payloads_sha256": canonical_sha256({sid: hashlib.sha256(raw).hexdigest() for sid, raw in evidence.items()}),
        "base_model_sha256": canonical_sha256(base), "label_grade_counts": dict(sorted(Counter(r["label_provenance"]["grade"] for r in train_rows).items())),
        "train_example_count": len(train_rows), "truth_counts": dict(sorted(truth_counts.items())),
        "optimization_steps": len(train_rows) * config["epochs"],
        "preselection_authority": "DECLARED_SOURCE_OBSERVATION_NOT_GOLD",
        "exposure_completeness": "DECLARED_NOT_INDEPENDENTLY_VERIFIED"}
    for field in ("split_validation_sha256", "train_examples_sha256", "train_rows_sha256",
                  "source_payloads_sha256", "evidence_payloads_sha256", "label_grade_counts", "train_example_count"):
        _require(pairwise._bytes(binding[field]) == pairwise._bytes(base["training_binding"][field]),
                 "BASE_TRAINING_BINDING_MISMATCH", field)
    _require(binding["optimization_steps"] <= MAX_OPTIMIZATION_STEPS, "OPTIMIZATION_BUDGET_INVALID")
    rows, row_reports = [], []
    for row in train_rows:
        assignment = row["assignment"]
        example = by_id[assignment["example_id"]]
        view, mapping = pairwise._bind_example(example, row, payloads, evidence,
            feature_schema=base_feature_schema, split_manifest=manifest)
        semantic_input = None
        if semantic:
            capture = pairwise._strict_capture(evidence[example["capture_sha256"]])
            semantic_input = pairwise._strict_capture(evidence[capture["semantic_input_sha256"]], maximum=pairwise.MAX_DATA_BYTES)
        view = _event_view(view)
        ids = [c["candidate_id"] for c in view["candidates"]]
        positives = [cid for cid, exposure in mapping.items() if exposure["polarity"] == "POSITIVE"]
        if assignment["truth_kind"] == "CANDIDATE":
            _require(assignment["binding_status"] == "UNIQUE" and len(positives) == 1
                     and mapping[positives[0]]["candidate_id"] == assignment["truth_label"], "TRAIN_POSITIVE_TRUTH_CONFLICT")
            target = ids.index(positives[0])
        else:
            _require(assignment["truth_label"] == NIL_LABEL and assignment["binding_status"] == "NOT_APPLICABLE"
                     and not positives and all(e["polarity"] == "NEGATIVE" for e in mapping.values()), "TRAIN_NIL_TRUTH_CONFLICT")
            target = len(ids)
        rows.append((_feature_vector(view), _candidate_scores(base, view, semantic_input=semantic_input,
            evidence_payloads=evidence if semantic else None), target))
        row_reports.append({"example_id": assignment["example_id"], "truth_kind": assignment["truth_kind"],
            "status": "USED_NIL_SOFTMAX", "candidate_count": len(ids), "label_grade": row["label_provenance"]["grade"]})
    if semantic:
        binding.update(pairwise._semantic_training_binding(examples, evidence))
        for field in ("semantic_feature_contract_sha256", "semantic_inputs_sha256"):
            _require(binding[field] == base["training_binding"][field], "BASE_SEMANTIC_BINDING_MISMATCH", field)
    weights = [0.0] * len(FEATURE_NAMES)
    initial_loss = _loss(weights, rows, config["l2"])
    for _ in range(config["epochs"]):
        factors = []
        for vector, candidates, target in rows:
            _, nil_mass = _distribution(candidates, pairwise._dot(weights, vector))
            factors.append(nil_mass - float(target == len(candidates)))
        gradient = [math.fsum(factor * row[0][j] for factor, row in zip(factors, rows)) / len(rows)
                    + config["l2"] * weights[j] for j in range(len(weights))]
        weights = [weight - config["learning_rate"] * grad for weight, grad in zip(weights, gradient)]
        _require(all(math.isfinite(weight) and abs(weight) <= MAX_WEIGHT for weight in weights), "OPTIMIZER_WEIGHT_LIMIT")
    final_loss = _loss(weights, rows, config["l2"])
    _require(math.isfinite(initial_loss) and math.isfinite(final_loss), "LOSS_NONFINITE")
    model = {"schema_version": MODEL_SCHEMA_V2 if semantic else MODEL_SCHEMA, "backend": BACKEND, "feature_schema": feature_schema,
        "data_kind": manifest["data_kind"], "feature_contract": contract, "feature_contract_sha256": canonical_sha256(contract),
        "base_model": base, "base_model_sha256": canonical_sha256(base), "config": config, "config_sha256": canonical_sha256(config),
        "weights": weights, "weights_sha256": canonical_sha256(weights), "training_binding": binding,
        "publication_authority": False, "probability_status": PROBABILITY_STATUS, "actual_performance_evaluated": False}
    model["model_sha256"] = canonical_sha256(model)
    model = validate_model(model)
    report = {"schema_version": REPORT_SCHEMA_V2 if semantic else REPORT_SCHEMA, "status": "TRAINED_NIL_AUGMENTED_LINEAR", "backend": BACKEND,
        "data_kind": model["data_kind"], "model_sha256": canonical_sha256(model), "base_model_sha256": canonical_sha256(base),
        "base_parameters_updated": False, "split_validation": validation, "optimization_split": "TRAIN",
        "training_binding": binding, "epochs_completed": config["epochs"], "initial_loss": initial_loss,
        "final_loss": final_loss, "parameters_changed": any(weight != 0 for weight in weights), "rows": row_reports,
        "train_rows": len(rows), "candidate_rows": truth_counts["CANDIDATE"], "nil_rows": truth_counts["NIL"],
        "publication_authority": False, "actual_performance_evaluated": False, "formal_kpi_status": "NOT_ESTIMABLE",
        "probability_status": PROBABILITY_STATUS, "nil_probability": None, "selected_label": None,
        "limitations": ["RAW_LOGITS_NOT_CALIBRATED_PROBABILITIES", "NO_NIL_DECISION_OR_PUBLICATION",
            "EMPTY_OR_INCOMPLETE_CANDIDATE_SETS_REJECTED", "DECLARED_CAPTURE_TIME_AND_ANNOTATION_TRUTH_NOT_INDEPENDENTLY_VERIFIED",
            "NO_ACTUAL_QUALITY_EVALUATION", "LEXICAL_ROLE_LINEAR_BASELINE_NOT_NEURAL_SEMANTIC_MODEL"]}
    report["report_sha256"] = canonical_sha256(report)
    return {"model": model, "training_report": report}


def train_model(split_manifest, *, source_payloads, evidence_payloads, examples, config=None,
                feature_schema=FEATURE_SCHEMA):
    """CLI-compatible two-stage pure trainer; only the NIL stage adds parameters."""
    config = {} if config is None else _copy_json(config, 2048)
    _require(type(config) is dict and set(config) <= {"base", "nil_head"}, "CONFIG_INVALID")
    _require(feature_schema in (FEATURE_SCHEMA, FEATURE_SCHEMA_V2), "FEATURE_SCHEMA_UNSUPPORTED")
    base_config = _config(config.get("base"))
    nil_config = _config(config.get("nil_head"))
    base_result = pairwise.train_model(split_manifest, source_payloads=source_payloads,
        evidence_payloads=evidence_payloads, examples=examples, config=base_config,
        feature_schema=pairwise.FEATURE_SCHEMA_V2 if feature_schema == FEATURE_SCHEMA_V2 else pairwise.FEATURE_SCHEMA)
    result = train_nil_head(base_result["model"], split_manifest, source_payloads=source_payloads,
        evidence_payloads=evidence_payloads, examples=examples, config=nil_config, feature_schema=feature_schema)
    report = result["training_report"]
    report.pop("report_sha256")
    report["base_training_report"] = base_result["training_report"]
    report["workflow"] = "PAIRWISE_TRAIN_THEN_FROZEN_BASE_NIL_HEAD_TRAIN"
    report["report_sha256"] = canonical_sha256(report)
    return result
