"""A bounded CPU pairwise linear baseline, never a score lookup or NIL model.

Supplied source/capture bytes prove binding, not annotation truth or capture time.
No filesystem, network, dynamic backend registration, or publication authority.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import re
import unicodedata

from .reranker_training_split import validate_training_split

BACKEND = "PAIRWISE_LINEAR_V1"
MODEL_SCHEMA = "candidate_reranker_learned_model_v1"
FEATURE_SCHEMA = "candidate_reranker_pairwise_features_v1"
CAPTURE_SCHEMA = "reranker_preselection_capture_v1"
REPORT_SCHEMA = "candidate_reranker_training_report_v1"
MODEL_SCHEMA_V2 = "candidate_reranker_learned_model_v2"
FEATURE_SCHEMA_V2 = "candidate_reranker_pairwise_features_v2"
CAPTURE_SCHEMA_V2 = "reranker_preselection_capture_v2"
REPORT_SCHEMA_V2 = "candidate_reranker_training_report_v2"
DEFAULT_CONFIG = {"epochs": 80, "learning_rate": 0.2, "l2": 0.01}
FEATURE_NAMES = (
    "title_substring", "alias_substring", "title_token_recall", "alias_token_recall",
    "title_bigram_jaccard", "alias_bigram_jaccard", "role_primary", "role_previous",
    "role_mentioned", "role_comparison", "role_unknown",
)
MAX_MODEL_BYTES = 64 * 1024
MAX_DATA_BYTES = 8 * 1024 * 1024
MAX_TRAIN_EXAMPLES = 256
MAX_PAIRS = 10000
MAX_PAIR_STEPS = 200000
MAX_WEIGHT = 100.0
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SPAN_FIELDS = {"source_id", "raw_path", "utf8_byte_span_start", "utf8_byte_span_end", "text", "span_sha256"}
_BINDING_FIELDS = {
    "split_manifest_sha256", "split_validation_sha256", "train_examples_sha256",
    "train_rows_sha256", "source_payloads_sha256", "evidence_payloads_sha256",
    "label_grade_counts", "train_example_count", "pair_count", "optimization_steps",
    "preselection_authority", "exposure_completeness",
}


def _contract(feature_schema=FEATURE_SCHEMA) -> dict:
    if feature_schema not in (FEATURE_SCHEMA, FEATURE_SCHEMA_V2):
        raise ValueError("FEATURE_SCHEMA_UNSUPPORTED")
    value = {"schema_version": feature_schema, "stage": "PRE_SELECTION",
            "feature_names": list(FEATURE_NAMES), "normalization": "NFKC_CASEFOLD",
            "tokens": "UNICODE_ALNUM_EXCLUDING_UNDERSCORE_V1", "character_ngrams": 2,
            "unicode_version": unicodedata.unidata_version,
            "role_authority": "SOURCE_OBSERVATION_NOT_GOLD",
            "excluded": ["candidate_id", "gold_label", "final_selection", "urls", "label_role_annotations"],
            "publication_authority": False}
    if feature_schema == FEATURE_SCHEMA_V2:
        from .candidate_reranker_semantic_input import FEATURE_CONTRACT, FEATURE_CONTRACT_SHA256
        value.update(semantic_input_contract=json.loads(json.dumps(FEATURE_CONTRACT)),
                     semantic_input_contract_sha256=FEATURE_CONTRACT_SHA256)
    return value


FEATURE_CONTRACT = _contract()


class LearnedRerankerError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(code + (": " + detail if detail else ""))


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise LearnedRerankerError(code, detail)


def _bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(value) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _copy_json(value, limit=MAX_DATA_BYTES):
    # Check shape before serialization, including cycles and non-JSON objects.
    nodes, chars, active = 0, 0, set()

    def walk(item, depth):
        nonlocal nodes, chars
        nodes += 1
        _require(nodes <= 200000 and depth <= 24, "JSON_LIMIT")
        if type(item) is str:
            chars += len(item)
            _require(chars <= limit, "JSON_LIMIT")
        elif item is None or type(item) in (int, bool):
            if type(item) is int:
                _require(abs(item) <= 2**63 - 1, "JSON_INTEGER_LIMIT")
        elif type(item) is float:
            _require(math.isfinite(item), "NONFINITE_NUMBER")
        elif type(item) in (dict, list):
            marker = id(item)
            _require(marker not in active, "JSON_CYCLE")
            _require(len(item) <= 10000, "JSON_LIMIT")
            active.add(marker)
            if type(item) is dict:
                for key, child in item.items():
                    _require(type(key) is str, "JSON_KEY_INVALID")
                    walk(key, depth + 1)
                    walk(child, depth + 1)
            else:
                for child in item:
                    walk(child, depth + 1)
            active.remove(marker)
        else:
            raise LearnedRerankerError("JSON_TYPE_INVALID")

    walk(value, 0)
    try:
        raw = _bytes(value)
    except (UnicodeError, ValueError, OverflowError) as exc:
        raise LearnedRerankerError("JSON_ENCODING_INVALID") from exc
    _require(len(raw) <= limit, "JSON_BYTE_LIMIT")
    return json.loads(raw)


def _object(value, keys, code="SCHEMA_INVALID"):
    _require(type(value) is dict and set(value) == set(keys), code)
    return value


def _hash(value):
    _require(type(value) is str and _SHA.fullmatch(value) is not None, "SHA_INVALID")
    return value


def _number(value, lower, upper):
    _require(type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper, "NUMBER_INVALID")
    return float(value)


def _config(value):
    value = {} if value is None else _copy_json(value, 1024)
    _require(type(value) is dict and set(value) <= set(DEFAULT_CONFIG), "CONFIG_INVALID")
    result = {"epochs": 80, "learning_rate": 0.2, "l2": 0.01, **value}
    _require(type(result["epochs"]) is int and 1 <= result["epochs"] <= 200, "EPOCH_LIMIT")
    _number(result["learning_rate"], 0.000001, 1.0)
    _number(result["l2"], 0.0, 1.0)
    return result


def _payloads(values):
    _require(type(values) is dict and len(values) <= 10000, "PAYLOAD_MAP_INVALID")
    _require(all(type(key) is str and 0 < len(key) <= 512 and type(raw) is bytes for key, raw in values.items()), "PAYLOAD_TYPE_INVALID")
    _require(sum(len(raw) for raw in values.values()) <= MAX_DATA_BYTES, "PAYLOAD_BYTE_LIMIT")
    return dict(values)


def _strict_capture(raw, *, maximum=MAX_MODEL_BYTES):
    _require(type(raw) is bytes and len(raw) <= maximum, "CAPTURE_BYTE_LIMIT")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "CAPTURE_DUPLICATE_KEY")
            result[key] = value
        return result

    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(LearnedRerankerError("NONFINITE_NUMBER")))
        return _copy_json(parsed, maximum)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise LearnedRerankerError("CAPTURE_JSON_INVALID") from exc


def _view(value, *, allow_empty=False):
    # Local import avoids a cycle when the existing adapter loads this backend.
    from .candidate_reranker_shadow import _validate_view
    view = _validate_view(value)
    _require(view["generation_status"] == "COMPLETE", "GENERATION_NOT_COMPLETE")
    _require(allow_empty or bool(view["candidates"]), "EMPTY_CANDIDATES")
    _require(any(fragment["text"].strip() for fragment in view["source_view"]["fragments"]), "EMPTY_QUERY")
    return view


def _normalize(text):
    return unicodedata.normalize("NFKC", text).casefold()


def _tokens(text):
    return set(re.findall(r"[^\W_]+", text, flags=re.UNICODE))


def _grams(text):
    text = "".join(text.split())
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _features(view):
    query = _normalize("\n".join(fragment["text"] for fragment in view["source_view"]["fragments"]))
    query_tokens, query_grams = _tokens(query), _grams(query)

    def lexical(texts):
        exact, overlap, grams = 0.0, 0.0, 0.0
        for raw in texts:
            text = _normalize(raw).strip()
            tokens, bigrams = _tokens(text), _grams(text)
            exact = max(exact, float(bool(text) and text in query))
            overlap = max(overlap, len(tokens & query_tokens) / len(tokens) if tokens else 0.0)
            union = bigrams | query_grams
            grams = max(grams, len(bigrams & query_grams) / len(union) if union else 0.0)
        return exact, overlap, grams

    result = []
    for candidate in view["candidates"]:
        titles, aliases = lexical(candidate["titles"]), lexical(candidate["aliases"])
        roles = {item["role"] for item in candidate["role_observations"]}
        result.append((titles[0], aliases[0], titles[1], aliases[1], titles[2], aliases[2],
                       *(float(role in roles) for role in ("PRIMARY", "PREVIOUS", "MENTIONED", "COMPARISON", "UNKNOWN"))))
    return result


def validate_model(model) -> dict:
    model = _copy_json(model, MAX_MODEL_BYTES)
    _object(model, {"schema_version", "backend", "feature_schema", "data_kind", "feature_contract",
                    "feature_contract_sha256", "config", "config_sha256", "weights", "weights_sha256",
                    "training_binding", "publication_authority", "probability_status",
                    "actual_performance_evaluated", "model_sha256"})
    semantic = model["schema_version"] == MODEL_SCHEMA_V2
    feature_schema = FEATURE_SCHEMA_V2 if semantic else FEATURE_SCHEMA
    _require(model["schema_version"] == (MODEL_SCHEMA_V2 if semantic else MODEL_SCHEMA)
             and model["backend"] == BACKEND and model["feature_schema"] == feature_schema, "MODEL_VERSION_INVALID")
    contract = _contract(feature_schema)
    _require(model["data_kind"] in ("SOURCE_BACKED", "SYNTHETIC_FIXTURE"), "DATA_KIND_INVALID")
    _require(_bytes(model["feature_contract"]) == _bytes(contract), "FEATURE_CONTRACT_INVALID")
    _require(model["feature_contract_sha256"] == canonical_sha256(contract), "FEATURE_SHA_MISMATCH")
    _object(model["config"], DEFAULT_CONFIG, "CONFIG_INVALID")
    _require(model["config"] == _config(model["config"]), "CONFIG_INVALID")
    _require(model["config_sha256"] == canonical_sha256(model["config"]), "CONFIG_SHA_MISMATCH")
    weights = model["weights"]
    _require(type(weights) is list and len(weights) == len(FEATURE_NAMES), "WEIGHTS_INVALID")
    for weight in weights:
        _number(weight, -MAX_WEIGHT, MAX_WEIGHT)
    _require(model["weights_sha256"] == canonical_sha256(weights), "WEIGHTS_SHA_MISMATCH")
    binding_fields = _BINDING_FIELDS | ({"semantic_feature_contract_sha256", "semantic_inputs_sha256"} if semantic else set())
    binding = _object(model["training_binding"], binding_fields)
    for field in binding_fields:
        if field.endswith("sha256"):
            _hash(binding[field])
    if semantic:
        _require(binding["semantic_feature_contract_sha256"] == contract["semantic_input_contract_sha256"],
                 "SEMANTIC_FEATURE_CONTRACT_MISMATCH")
    _require(type(binding["train_example_count"]) is int and 1 <= binding["train_example_count"] <= MAX_TRAIN_EXAMPLES,
             "TRAIN_EXAMPLE_LIMIT")
    _require(type(binding["pair_count"]) is int and 1 <= binding["pair_count"] <= MAX_PAIRS, "PAIR_LIMIT")
    steps = binding["pair_count"] * model["config"]["epochs"]
    _require(type(binding["optimization_steps"]) is int and binding["optimization_steps"] == steps <= MAX_PAIR_STEPS,
             "OPTIMIZATION_BUDGET_INVALID")
    grades = binding["label_grade_counts"]
    _require(type(grades) is dict and bool(grades) and set(grades) <= {"MODEL_REFERENCE", "GOLD_LITE", "HUMAN_GOLD", "SYNTHETIC_FIXTURE"},
             "LABEL_GRADES_INVALID")
    _require(all(type(count) is int and count > 0 for count in grades.values())
             and sum(grades.values()) == binding["train_example_count"], "LABEL_GRADES_INVALID")
    _require(model["data_kind"] == "SYNTHETIC_FIXTURE" or "SYNTHETIC_FIXTURE" not in grades, "LABEL_DATA_KIND_CONFLICT")
    _require(binding["preselection_authority"] == "DECLARED_SOURCE_OBSERVATION_NOT_GOLD"
             and binding["exposure_completeness"] == "DECLARED_NOT_INDEPENDENTLY_VERIFIED", "AUTHORITY_INVALID")
    _require(model["publication_authority"] is False and model["actual_performance_evaluated"] is False
             and model["probability_status"] == "NOT_AVAILABLE_UNCALIBRATED", "AUTHORITY_INVALID")
    digest = _hash(model["model_sha256"])
    _require(digest == canonical_sha256({key: value for key, value in model.items() if key != "model_sha256"}), "MODEL_SHA_MISMATCH")
    return model


def _score_semantic_input(model, view, semantic_input, evidence_payloads):
    if model["feature_schema"] == FEATURE_SCHEMA:
        _require(semantic_input is None and evidence_payloads is None, "V1_SEMANTIC_INPUT_FORBIDDEN")
        return None
    _require(semantic_input is not None, "SEMANTIC_INPUT_REQUIRED")
    from .candidate_reranker_semantic_input import validate_semantic_input
    return validate_semantic_input(semantic_input, evidence_payloads=evidence_payloads, expected_view=view)


def score_view(model, validated_frozen_view, *, semantic_input=None, evidence_payloads=None) -> list[dict]:
    model, view = validate_model(model), _view(validated_frozen_view)
    _score_semantic_input(model, view, semantic_input, evidence_payloads)
    rows = [{"candidate_id": candidate["candidate_id"],
             "score": math.fsum(weight * feature for weight, feature in zip(model["weights"], vector))}
            for candidate, vector in zip(view["candidates"], _features(view))]
    _require(all(math.isfinite(row["score"]) for row in rows), "SCORE_NONFINITE")
    return sorted(rows, key=lambda row: -row["score"])


def _span(value, payloads, allowed_sources):
    value = _object(value, _SPAN_FIELDS, "TEXT_SPAN_SCHEMA_INVALID")
    sid, start, end, text = value["source_id"], value["utf8_byte_span_start"], value["utf8_byte_span_end"], value["text"]
    _require(type(sid) is str and sid in allowed_sources and sid in payloads, "TEXT_SOURCE_NOT_BOUND")
    _require(type(value["raw_path"]) is str and value["raw_path"].startswith("/"), "TEXT_PATH_INVALID")
    _require(type(text) is str and 0 < len(text) <= 12000, "TEXT_INVALID")
    _require(type(start) is int and type(end) is int and 0 <= start < end <= len(payloads[sid]), "TEXT_BYTE_SPAN_INVALID")
    raw = text.encode("utf-8")
    _require(payloads[sid][start:end] == raw and end - start == len(raw), "TEXT_SOURCE_MISMATCH")
    _require(_hash(value["span_sha256"]) == hashlib.sha256(raw).hexdigest(), "TEXT_SHA_MISMATCH")
    return value


def _bind_example(example, row, payloads, evidence, *, feature_schema=FEATURE_SCHEMA, split_manifest=None):
    _require(feature_schema in (FEATURE_SCHEMA, FEATURE_SCHEMA_V2), "FEATURE_SCHEMA_UNSUPPORTED")
    _object(example, {"example_id", "frozen_view", "candidate_text_bindings", "capture_sha256"}, "EXAMPLE_SCHEMA_INVALID")
    assignment = row["assignment"]
    view = _view(example["frozen_view"], allow_empty=True)
    _require(example["example_id"] == assignment["example_id"] and view["post_id"] == assignment["post_id"], "EXAMPLE_ROW_MISMATCH")
    fragments = view["source_view"]["fragments"]
    expected_fragments = [{"raw_path": span["raw_path"], "text": span["text"]} for span in row["source_spans"]]
    _require([{key: fragment[key] for key in ("raw_path", "text")} for fragment in fragments] == expected_fragments,
             "QUERY_SOURCE_MISMATCH")
    # The view validator binds role character spans to fragments; those fragments
    # are now bound to validated source UTF-8 byte spans, without offset coercion.
    namespace = view["candidate_namespace"]
    exposures = row["exposures"]
    key = "corpus_candidate_id" if namespace == "CORPUS_CANDIDATE" else "candidate_id"
    ids = [item[key] for item in exposures]
    _require(all(type(cid) is str for cid in ids) and len(ids) == len(set(ids)), "EXPOSURE_ID_MAP_INVALID")
    candidates = view["candidates"]
    _require({item["candidate_id"] for item in candidates} == set(ids), "EXPOSURE_SET_MISMATCH")
    if namespace == "CANDIDATE_OPTION":
        _require(view["candidate_set_fingerprint"] == assignment["candidate_set_fingerprint"], "CANDIDATE_SET_SHA_MISMATCH")
    mapping = {item[key]: item for item in exposures}
    bindings = example["candidate_text_bindings"]
    _require(type(bindings) is list and len(bindings) == len(candidates), "TEXT_BINDING_COUNT_MISMATCH")
    for candidate, bound in zip(candidates, bindings):
        _object(bound, {"candidate_id", "titles", "aliases"}, "TEXT_BINDING_SCHEMA_INVALID")
        _require(bound["candidate_id"] == candidate["candidate_id"], "TEXT_CANDIDATE_MISMATCH")
        for field in ("titles", "aliases"):
            _require(type(bound[field]) is list and len(bound[field]) == len(candidate[field]), "TEXT_BINDING_COUNT_MISMATCH")
            texts = [_span(span, payloads, mapping[candidate["candidate_id"]]["source_ids"])["text"] for span in bound[field]]
            _require(texts == candidate[field], "CANDIDATE_TEXT_MISMATCH")
    capture_sha = _hash(example["capture_sha256"])
    _require(capture_sha in evidence and hashlib.sha256(evidence[capture_sha]).hexdigest() == capture_sha, "CAPTURE_BYTES_MISMATCH")
    label_shas = {row["label_provenance"]["artifact_sha256"], *(item["provenance"]["artifact_sha256"] for item in row["role_mentions"])}
    _require(capture_sha not in label_shas, "LABEL_AS_FEATURE_CAPTURE")
    capture = _strict_capture(evidence[capture_sha])
    semantic = feature_schema == FEATURE_SCHEMA_V2
    expected = {"schema_version": CAPTURE_SCHEMA_V2 if semantic else CAPTURE_SCHEMA,
                "stage": "PRE_SELECTION", "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD",
                "example_id": assignment["example_id"], "post_id": assignment["post_id"], "binding": row["binding"],
                "source_spans_sha256": canonical_sha256(row["source_spans"]),
                "candidate_set_fingerprint": assignment["candidate_set_fingerprint"],
                "frozen_view_sha256": canonical_sha256(view),
                "candidate_text_bindings_sha256": canonical_sha256(bindings)}
    if semantic:
        expected["semantic_input_sha256"] = _hash(capture.get("semantic_input_sha256"))
    _require(_bytes(capture) == _bytes(expected), "PRESELECTION_CAPTURE_MISMATCH")
    if semantic:
        _require(capture["semantic_input_sha256"] not in label_shas, "LABEL_AS_SEMANTIC_INPUT")
        from .candidate_reranker_semantic_input import resolve_training_semantic_input
        resolve_training_semantic_input(capture, view, row, payloads, evidence, split_manifest=split_manifest)
    return view, mapping


def _semantic_training_binding(examples, evidence):
    """TRAIN 재생을 통과한 artifact의 self SHA 집합을 순서 독립적으로 묶는다."""
    from .candidate_reranker_semantic_input import FEATURE_CONTRACT_SHA256
    inputs = []
    for example in examples:
        capture = _strict_capture(evidence[example["capture_sha256"]])
        artifact_raw = evidence[_hash(capture["semantic_input_sha256"])]
        _require(hashlib.sha256(artifact_raw).hexdigest() == capture["semantic_input_sha256"], "SEMANTIC_INPUT_BYTES_MISMATCH")
        artifact = _strict_capture(artifact_raw, maximum=MAX_DATA_BYTES)
        inputs.append(_hash(artifact["input_sha256"]))
    return {"semantic_feature_contract_sha256": FEATURE_CONTRACT_SHA256,
            "semantic_inputs_sha256": canonical_sha256(sorted(inputs))}


def _dot(weights, vector):
    return math.fsum(weight * value for weight, value in zip(weights, vector))


def _loss(weights, pairs, l2):
    margins = [-_dot(weights, vector) for vector in pairs]
    return math.fsum(max(value, 0.0) + math.log1p(math.exp(-abs(value))) for value in margins) / len(pairs) + l2 * _dot(weights, weights) / 2


def train_model(split_manifest, *, source_payloads, evidence_payloads, examples, config=None,
                feature_schema=FEATURE_SCHEMA) -> dict:
    """Optimize TRAIN only after the complete four-way exposure gate is VALID."""
    manifest, examples = _copy_json(split_manifest), _copy_json(examples)
    _require(feature_schema in (FEATURE_SCHEMA, FEATURE_SCHEMA_V2), "FEATURE_SCHEMA_UNSUPPORTED")
    semantic = feature_schema == FEATURE_SCHEMA_V2
    contract = _contract(feature_schema)
    payloads, evidence, config = _payloads(source_payloads), _payloads(evidence_payloads), _config(config)
    _require(sum(map(len, payloads.values())) + sum(map(len, evidence.values())) <= MAX_DATA_BYTES, "PAYLOAD_BYTE_LIMIT")
    validation = validate_training_split(manifest, source_payloads=payloads, evidence_payloads=evidence)
    _require(validation["status"] == "VALID", "FULL_SPLIT_NOT_VALID", ",".join(sorted({item["code"] for item in validation["issues"]})))
    rows = sorted((row for row in manifest["rows"] if row["assignment"]["split"] == "TRAIN"), key=lambda row: row["assignment"]["example_id"])
    _require(1 <= len(rows) <= MAX_TRAIN_EXAMPLES, "TRAIN_EXAMPLE_LIMIT")
    _require(type(examples) is list and len(examples) == len(rows), "TRAIN_EXAMPLE_SET_MISMATCH")
    for example in examples:
        _object(example, {"example_id", "frozen_view", "candidate_text_bindings", "capture_sha256"}, "EXAMPLE_SCHEMA_INVALID")
        _require(type(example["example_id"]) is str, "EXAMPLE_ID_INVALID")
    by_id = {example["example_id"]: example for example in examples}
    _require(len(by_id) == len(examples) and set(by_id) == {row["assignment"]["example_id"] for row in rows}, "TRAIN_EXAMPLE_SET_MISMATCH")
    pairs, row_reports = [], []
    for row in rows:
        assignment = row["assignment"]
        view, mapping = _bind_example(by_id[assignment["example_id"]], row, payloads, evidence,
                                      feature_schema=feature_schema, split_manifest=manifest)
        vectors = {candidate["candidate_id"]: vector for candidate, vector in zip(view["candidates"], _features(view))}
        positives = [cid for cid, exposure in mapping.items() if exposure["polarity"] == "POSITIVE"]
        negatives = [cid for cid, exposure in mapping.items() if exposure["polarity"] == "NEGATIVE"]
        if assignment["truth_kind"] == "CANDIDATE":
            _require(len(positives) == 1 and mapping[positives[0]]["candidate_id"] == assignment["truth_label"], "TRAIN_POSITIVE_TRUTH_CONFLICT")
        count = 0
        # Sort only to make aggregation deterministic; identities are not features.
        for positive in sorted(positives):
            for negative in sorted(negatives):
                pairs.append(tuple(a - b for a, b in zip(vectors[positive], vectors[negative])))
                count += 1
        row_reports.append({"example_id": assignment["example_id"], "truth_kind": assignment["truth_kind"],
                            "status": "USED_PAIRWISE" if count else ("NO_PAIR_NIL" if assignment["truth_kind"] == "NIL" else "NO_NEGATIVE"),
                            "pair_count": count, "label_grade": row["label_provenance"]["grade"]})
    _require(bool(pairs), "NO_TRAINABLE_PAIRS")
    _require(len(pairs) <= MAX_PAIRS and len(pairs) * config["epochs"] <= MAX_PAIR_STEPS, "OPTIMIZATION_BUDGET_INVALID")
    semantic_binding = _semantic_training_binding(examples, evidence) if semantic else {}
    weights = [0.0] * len(FEATURE_NAMES)
    initial_loss = _loss(weights, pairs, config["l2"])
    for _ in range(config["epochs"]):
        factors = []
        for vector in pairs:
            margin = _dot(weights, vector)
            exp = math.exp(-abs(margin))
            factors.append(exp / (1 + exp) if margin >= 0 else 1 / (1 + exp))
        gradient = [(-math.fsum(factor * vector[j] for factor, vector in zip(factors, pairs)) / len(pairs)
                     + config["l2"] * weights[j]) for j in range(len(weights))]
        weights = [weight - config["learning_rate"] * grad for weight, grad in zip(weights, gradient)]
        _require(all(math.isfinite(weight) and abs(weight) <= MAX_WEIGHT for weight in weights), "OPTIMIZER_WEIGHT_LIMIT")
    binding = {"split_manifest_sha256": manifest["manifest_sha256"], "split_validation_sha256": validation["report_sha256"],
               "train_examples_sha256": canonical_sha256([by_id[row["assignment"]["example_id"]] for row in rows]),
               "train_rows_sha256": canonical_sha256(rows),
               "source_payloads_sha256": canonical_sha256({sid: hashlib.sha256(raw).hexdigest() for sid, raw in payloads.items()}),
               "evidence_payloads_sha256": canonical_sha256({sid: hashlib.sha256(raw).hexdigest() for sid, raw in evidence.items()}),
               "label_grade_counts": dict(sorted(Counter(row["label_provenance"]["grade"] for row in rows).items())),
               "train_example_count": len(rows), "pair_count": len(pairs), "optimization_steps": len(pairs) * config["epochs"],
               "preselection_authority": "DECLARED_SOURCE_OBSERVATION_NOT_GOLD", "exposure_completeness": "DECLARED_NOT_INDEPENDENTLY_VERIFIED"}
    binding.update(semantic_binding)
    model = {"schema_version": MODEL_SCHEMA_V2 if semantic else MODEL_SCHEMA, "backend": BACKEND, "feature_schema": feature_schema,
             "data_kind": manifest["data_kind"], "feature_contract": contract, "feature_contract_sha256": canonical_sha256(contract),
             "config": config, "config_sha256": canonical_sha256(config), "weights": weights, "weights_sha256": canonical_sha256(weights),
             "training_binding": binding, "publication_authority": False, "probability_status": "NOT_AVAILABLE_UNCALIBRATED",
             "actual_performance_evaluated": False}
    model["model_sha256"] = canonical_sha256(model)
    model = validate_model(model)
    report = {"schema_version": REPORT_SCHEMA_V2 if semantic else REPORT_SCHEMA, "backend": BACKEND, "data_kind": manifest["data_kind"],
              "status": "TRAINED_PAIRWISE_LINEAR", "model_sha256": canonical_sha256(model),
              "split_validation": validation, "optimization_split": "TRAIN", "training_binding": binding,
              "epochs_completed": config["epochs"], "initial_loss": initial_loss, "final_loss": _loss(weights, pairs, config["l2"]),
              "parameters_changed": any(weight != 0 for weight in weights), "rows": row_reports,
              "train_rows": len(rows), "pair_rows": sum(item["pair_count"] > 0 for item in row_reports),
              "nil_rows": sum(item["truth_kind"] == "NIL" for item in row_reports),
              "publication_authority": False, "actual_performance_evaluated": False,
              "formal_kpi_status": "NOT_ESTIMABLE", "nil_probability": None,
              "probability_status": "NOT_AVAILABLE_UNCALIBRATED",
              "limitations": ["LEXICAL_ROLE_LINEAR_BASELINE_NOT_NEURAL_SEMANTIC_MODEL", "NO_NIL_HEAD",
                              "NO_CALIBRATION_OR_HOLDOUT_EVALUATION", "CAPTURE_TIME_AND_ANNOTATION_TRUTH_NOT_INDEPENDENTLY_VERIFIED"]}
    report["report_sha256"] = canonical_sha256(report)
    return {"model": model, "training_report": report}
