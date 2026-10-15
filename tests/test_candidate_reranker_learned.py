"""실자료 정확도 대신 합성 원문/관측/학습 파라미터의 계약을 검증한다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_batch.grounding import candidate_reranker_learned as learned
from llm_batch.grounding import reranker_training_split as split


def _raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _capture(bundle, example=None):
    manifest, _, evidence, examples = bundle
    example = examples[0] if example is None else example
    row = next(item for item in manifest["rows"] if item["assignment"]["example_id"] == example["example_id"])
    capture = {"schema_version": learned.CAPTURE_SCHEMA, "stage": "PRE_SELECTION",
               "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD", "example_id": example["example_id"],
               "post_id": row["assignment"]["post_id"], "binding": row["binding"],
               "source_spans_sha256": learned.canonical_sha256(row["source_spans"]),
               "candidate_set_fingerprint": row["assignment"]["candidate_set_fingerprint"],
               "frozen_view_sha256": learned.canonical_sha256(example["frozen_view"]),
               "candidate_text_bindings_sha256": learned.canonical_sha256(example["candidate_text_bindings"])}
    raw = _raw(capture)
    example["capture_sha256"] = _sha(raw)
    evidence[example["capture_sha256"]] = raw
    return capture


def training_fixture(*, include_nil=False):
    """Public factory: four isolated synthetic splits and one TRAIN capture.

    Returns (manifest, source_payloads, evidence_payloads, examples). Role feature
    observations and label annotations are explicitly separate byte artifacts.
    """
    sources, rows, payloads, evidence, examples = [], [], {}, {}, []
    partitions = (*split.SPLITS, "TRAIN") if include_nil else split.SPLITS
    for i, partition in enumerate(partitions):
        sid, post = f"learned-source-{i}", str(500 + i)
        titles = [f"별빛주작품{i}", f"비교소설{i}"]
        text = f"이 글의 대상은 {titles[0]}입니다. 예전 {titles[1]}과 비교합니다."
        raw = text.encode("utf-8")
        payloads[sid] = raw
        sources.append({"source_id": sid, "payload_sha256": _sha(raw), "source_group_id": f"learned-group-{i}",
                        "lineage_root_id": f"learned-lineage-{i}", "rights_status": "SYNTHETIC_FIXTURE"})
        annotation = _raw({"schema_version": "synthetic_label_annotation", "split": partition, "author": "synthetic fixture author",
                           "identity": titles[0], "roles": ["PRIMARY", "COMPARISON"]})
        label_sha = _sha(annotation)
        evidence[label_sha] = annotation
        original = {"source_id": sid, "raw_path": "/content", "utf8_byte_span_start": 0, "utf8_byte_span_end": len(raw),
                    "text": text, "span_sha256": _sha(raw)}
        exposures, mentions, bridges, candidates, text_bindings = [], [], [], [], []
        for j, title in enumerate(titles):
            cid, corpus = f"learned-option-{i}-{j}", f"learned-corpus-{i}-{j}"
            role = "PRIMARY" if j == 0 else "COMPARISON"
            start = raw.index(title.encode("utf-8"))
            span = {**original, "utf8_byte_span_start": start, "utf8_byte_span_end": start + len(title.encode("utf-8")),
                    "text": title, "span_sha256": _sha(title.encode("utf-8"))}
            exposures.append({"candidate_id": cid, "corpus_candidate_id": corpus, "polarity": "POSITIVE" if j == 0 and i != 4 else "NEGATIVE",
                              "work_id": f"learned-work-{i}-{j}", "edition_id": f"learned-edition-{i}-{j}", "media_type": "WEB_NOVEL",
                              "alias_family_ids": [f"learned-alias-{i}-{j}"], "source_ids": [sid]})
            bridges.append({"corpus_candidate_id": corpus, "status": "UNIQUE", "candidate_ids": [cid], "provenance_sha256": label_sha})
            mentions.append({"candidate_id": cid, "source_span": span, "roles": [role],
                             "provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": label_sha,
                                            "reviewer": "synthetic author", "scope": "MENTION_ROLE"}})
            char_start = text.index(title)
            candidates.append({"candidate_id": corpus, "titles": [title], "urls": [], "aliases": [], "option_kind": "WORK_CANDIDATE",
                               "event_eligible": True, "identity_conflict": False, "negative_evidence": [],
                               "role_observations": [{"role": role, "raw_path": "/content", "start": char_start,
                                                      "end": char_start + len(title), "text_sha256": span["span_sha256"]}]})
            text_bindings.append({"candidate_id": corpus, "titles": [deepcopy(span)], "aliases": []})
        assignment = {"example_id": f"learned-example-{i}", "post_id": post, "split_group_id": f"learned-split-{i}",
                      "content_fingerprint": split.canonical_sha256([original]), "source_group_fingerprint": split.canonical_sha256([f"learned-group-{i}"]),
                      "split": partition, "truth_kind": "CANDIDATE", "truth_label": exposures[0]["candidate_id"],
                      "label_provenance_sha256": label_sha, "candidate_set_fingerprint": split.canonical_sha256(exposures),
                      "gold_work_fingerprint": split.canonical_sha256(exposures[0]["work_id"]),
                      "binding_status": "UNIQUE", "matched_candidate_ids": [exposures[0]["candidate_id"]]}
        if i == 4:
            assignment.update(truth_kind="NIL", truth_label="__NIL__", gold_work_fingerprint=None,
                              binding_status="NOT_APPLICABLE", matched_candidate_ids=[])
        rows.append({"assignment": assignment, "binding": {"run_id": "synthetic-learned-run", "attempt_id": f"learned-attempt-{i}", "input_index": i + 1},
                     "source_ids": [sid], "source_spans": [original], "exposures": exposures, "r2_id_bridges": bridges, "role_mentions": mentions,
                     "label_provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": label_sha, "reviewer": "synthetic author", "scope": "WORK_IDENTITY"}})
        if partition == "TRAIN":
            view = {"schema_version": "candidate_reranker_frozen_view_v1", "stage": "PRE_SELECTION", "post_id": post,
                    "source_view": {"schema_version": "candidate_retrieval_source_view_v1", "post_id": post,
                                    "fragments": [{"raw_path": "/content", "kind": "BODY", "text": text}]},
                    "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": _sha(b"synthetic preselection generation"),
                    "candidate_set_fingerprint": None, "generation_status": "COMPLETE", "candidates": candidates}
            examples.append({"example_id": assignment["example_id"], "frozen_view": view,
                             "candidate_text_bindings": text_bindings, "capture_sha256": None})
    manifest = split.seal_manifest({"schema_version": split.SCHEMA_VERSION, "data_kind": "SYNTHETIC_FIXTURE",
                                    "split_policy_version": split.POLICY_VERSION, "sources": sources, "rows": rows})
    bundle = (manifest, payloads, evidence, examples)
    for example in examples:
        _capture(bundle, example)
    return bundle


def _train(bundle=None, config=None):
    manifest, payloads, evidence, examples = training_fixture() if bundle is None else bundle
    return learned.train_model(manifest, source_payloads=payloads, evidence_payloads=evidence,
                               examples=examples, config={"epochs": 16} if config is None else config)


def _reseal(bundle):
    bundle[0]["manifest_sha256"] = split.seal_manifest(bundle[0])["manifest_sha256"]
    return bundle


def _model_seal(model):
    model["model_sha256"] = learned.canonical_sha256({key: value for key, value in model.items() if key != "model_sha256"})
    return model


def test_optimizer_learns_parameters_and_decreases_pairwise_loss_without_io():
    bundle = training_fixture()
    before = deepcopy(bundle)
    with patch.object(Path, "open", side_effect=AssertionError("pure trainer must not open files")):
        result = _train(bundle)
    model, report = result["model"], result["training_report"]
    assert bundle == before
    assert any(weight != 0 for weight in model["weights"])
    assert report["final_loss"] < report["initial_loss"]
    assert report["parameters_changed"] is True
    assert report["split_validation"]["status"] == "VALID"
    assert report["optimization_split"] == "TRAIN" and report["train_rows"] == report["pair_rows"] == 1
    assert report["training_binding"]["pair_count"] == 1
    assert report["status"] == "TRAINED_PAIRWISE_LINEAR"
    assert model["backend"] == learned.BACKEND and model["data_kind"] == "SYNTHETIC_FIXTURE"
    assert report["nil_probability"] is None and report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert model["publication_authority"] is report["actual_performance_evaluated"] is False
    assert "scores" not in model
    rows = learned.score_view(model, bundle[3][0]["frozen_view"])
    assert rows[0]["candidate_id"] == "learned-corpus-0-0" and rows[0]["score"] > rows[1]["score"]


def test_deterministic_json_readback_copy_and_full_feature_contract():
    result = _train()
    assert result == _train()
    model = result["model"]
    loaded = learned.validate_model(json.loads(_raw(model)))
    assert loaded == model and loaded is not model
    loaded["weights"][0] += 1
    assert loaded != model
    assert model["feature_contract"] == learned.FEATURE_CONTRACT
    report = deepcopy(result["training_report"])
    digest = report.pop("report_sha256")
    assert learned.canonical_sha256(report) == digest


def test_unseen_id_and_post_do_not_change_scores_and_all_candidates_return_once():
    bundle = training_fixture()
    model, view = _train(bundle)["model"], bundle[3][0]["frozen_view"]
    original = learned.score_view(model, view)
    unseen = deepcopy(view)
    unseen["post_id"] = unseen["source_view"]["post_id"] = "unseen-post"
    unseen["candidates"][0]["candidate_id"] = "new-not-trained-z"
    unseen["candidates"][1]["candidate_id"] = "new-not-trained-a"
    scored = learned.score_view(model, unseen)
    assert [row["score"] for row in scored] == [row["score"] for row in original]
    assert {row["candidate_id"] for row in scored} == {"new-not-trained-z", "new-not-trained-a"}
    assert len(scored) == 2


def test_role_observation_affects_score_but_annotation_is_not_a_feature():
    bundle = training_fixture()
    original = _train(bundle)
    # Flip annotation roles without touching preselection capture observations.
    for mention in bundle[0]["rows"][0]["role_mentions"]:
        mention["roles"] = ["PREVIOUS"]
    changed = _train(_reseal(bundle))
    assert changed["model"]["weights"] == original["model"]["weights"]
    view = deepcopy(bundle[3][0]["frozen_view"])
    view["candidates"][0]["role_observations"][0]["role"] = "COMPARISON"
    before = learned.score_view(original["model"], bundle[3][0]["frozen_view"])
    after = {row["candidate_id"]: row["score"] for row in learned.score_view(original["model"], view)}
    assert after[before[0]["candidate_id"]] < before[0]["score"]


def test_dev_calibration_holdout_label_change_never_updates_weights():
    bundle = training_fixture()
    original = _train(bundle)
    for row in bundle[0]["rows"][1:]:
        row["exposures"][0]["polarity"], row["exposures"][1]["polarity"] = "NEGATIVE", "POSITIVE"
        assignment = row["assignment"]
        assignment["truth_label"] = row["exposures"][1]["candidate_id"]
        assignment["matched_candidate_ids"] = [assignment["truth_label"]]
        assignment["gold_work_fingerprint"] = split.canonical_sha256(row["exposures"][1]["work_id"])
    changed = _train(_reseal(bundle))
    assert original["model"]["weights"] == changed["model"]["weights"]
    assert original["model"]["training_binding"]["train_rows_sha256"] == changed["model"]["training_binding"]["train_rows_sha256"]
    assert original["model"]["training_binding"]["split_manifest_sha256"] != changed["model"]["training_binding"]["split_manifest_sha256"]


def test_train_label_direction_changes_actual_parameters():
    bundle = training_fixture()
    original = _train(bundle)["model"]
    row = bundle[0]["rows"][0]
    row["exposures"][0]["polarity"], row["exposures"][1]["polarity"] = "NEGATIVE", "POSITIVE"
    row["assignment"]["truth_label"] = row["exposures"][1]["candidate_id"]
    row["assignment"]["matched_candidate_ids"] = [row["assignment"]["truth_label"]]
    row["assignment"]["gold_work_fingerprint"] = split.canonical_sha256(row["exposures"][1]["work_id"])
    changed = _train(_reseal(bundle))["model"]
    assert changed["weights"] == [-weight for weight in original["weights"]]


def test_full_split_leak_gate_and_missing_holdout_are_never_bypassed():
    bundle = training_fixture()
    bundle[0]["rows"][1]["exposures"][1]["work_id"] = bundle[0]["rows"][0]["exposures"][1]["work_id"]
    with pytest.raises(learned.LearnedRerankerError, match="FULL_SPLIT_NOT_VALID.*CROSS_SPLIT_EXPOSURE"):
        _train(_reseal(bundle))
    bundle = training_fixture()
    bundle[0]["rows"].pop()
    with pytest.raises(learned.LearnedRerankerError, match="FULL_SPLIT_NOT_VALID"):
        _train(_reseal(bundle))


@pytest.mark.parametrize("mutation", ["text", "source_byte", "byte_offset", "candidate_id", "missing_candidate", "source_order", "post", "role_span"])
def test_resealed_capture_does_not_hide_source_candidate_or_role_binding_error(mutation):
    bundle = training_fixture()
    example = bundle[3][0]
    view = example["frozen_view"]
    if mutation == "text":
        view["candidates"][0]["titles"] = ["원문에 없는 제목"]
    elif mutation == "source_byte":
        bundle[1]["learned-source-0"] += b"changed"
    elif mutation == "byte_offset":
        example["candidate_text_bindings"][0]["titles"][0]["utf8_byte_span_start"] += 1
    elif mutation == "candidate_id":
        view["candidates"][0]["candidate_id"] = "different-unexposed-candidate"
    elif mutation == "missing_candidate":
        view["candidates"].pop()
        example["candidate_text_bindings"].pop()
    elif mutation == "source_order":
        view["source_view"]["fragments"][0]["text"] += " 덧붙임"
    elif mutation == "post":
        view["post_id"] = view["source_view"]["post_id"] = "foreign-post"
    elif mutation == "role_span":
        view["candidates"][0]["role_observations"][0]["start"] += 1
    _capture(bundle)
    with pytest.raises(ValueError):
        _train(bundle)


@pytest.mark.parametrize("field,value", [("stage", "POST_SELECTION"), ("feature_authority", "HUMAN_GOLD"), ("post_id", "foreign-post"),
                                         ("binding", {"run_id": "other", "attempt_id": "other", "input_index": 1})])
def test_correctly_hashed_wrong_preselection_receipt_is_rejected(field, value):
    bundle = training_fixture()
    capture = _capture(bundle)
    capture[field] = value
    raw = _raw(capture)
    bundle[3][0]["capture_sha256"] = _sha(raw)
    bundle[2][_sha(raw)] = raw
    with pytest.raises(learned.LearnedRerankerError, match="PRESELECTION_CAPTURE_MISMATCH"):
        _train(bundle)


def test_duplicate_capture_keys_and_label_capture_reuse_rejected():
    bundle = training_fixture()
    raw = bundle[2][bundle[3][0]["capture_sha256"]]
    raw = b'{"stage":"POST_SELECTION",' + raw[1:]
    bundle[3][0]["capture_sha256"] = _sha(raw)
    bundle[2][_sha(raw)] = raw
    with pytest.raises(learned.LearnedRerankerError, match="CAPTURE_DUPLICATE_KEY"):
        _train(bundle)
    bundle = training_fixture()
    bundle[3][0]["capture_sha256"] = bundle[0]["rows"][0]["label_provenance"]["artifact_sha256"]
    with pytest.raises(learned.LearnedRerankerError, match="LABEL_AS_FEATURE_CAPTURE"):
        _train(bundle)


@pytest.mark.parametrize("mutation", ["extra_holdout", "duplicate", "missing", "gold_feature"])
def test_exact_train_examples_and_no_gold_feature_fields(mutation):
    bundle = training_fixture()
    if mutation in {"extra_holdout", "duplicate"}:
        extra = deepcopy(bundle[3][0])
        if mutation == "extra_holdout":
            extra["example_id"] = bundle[0]["rows"][3]["assignment"]["example_id"]
        bundle[3].append(extra)
    elif mutation == "missing":
        bundle[3].clear()
    else:
        bundle[3][0]["frozen_view"]["candidates"][0]["gold"] = True
        _capture(bundle)
    with pytest.raises(ValueError):
        _train(bundle)


@pytest.mark.parametrize("config", [{"epochs": True}, {"epochs": 0}, {"epochs": 201}, {"learning_rate": 0},
                                    {"learning_rate": float("nan")}, {"l2": -1}, {"seed": 1}, {"backend": "IMPORT_CUSTOM"}])
def test_optimizer_config_limits(config):
    with pytest.raises(learned.LearnedRerankerError):
        _train(config=config)


@pytest.mark.parametrize("mutation", ["weight", "nonfinite", "extra_score_table", "feature", "authority", "config", "grade", "steps"])
def test_model_readback_rejects_even_resealed_invalid_contract(mutation):
    model = _train()["model"]
    if mutation == "weight":
        model["weights"][0] = 101.0
        model["weights_sha256"] = learned.canonical_sha256(model["weights"])
    elif mutation == "nonfinite":
        model["weights"][0] = float("inf")
    elif mutation == "extra_score_table":
        model["scores"] = {"candidate-1": 10}
    elif mutation == "feature":
        model["feature_contract"]["feature_names"][0] = "gold_label"
        model["feature_contract_sha256"] = learned.canonical_sha256(model["feature_contract"])
    elif mutation == "authority":
        model["publication_authority"] = True
    elif mutation == "config":
        model["config"]["epochs"] = 0
        model["config_sha256"] = learned.canonical_sha256(model["config"])
    elif mutation == "grade":
        model["training_binding"]["label_grade_counts"] = {"UNJUDGED": 1}
    elif mutation == "steps":
        model["training_binding"]["optimization_steps"] = True
    if mutation != "nonfinite":
        _model_seal(model)
    with pytest.raises(learned.LearnedRerankerError):
        learned.validate_model(model)


def test_modified_model_requires_all_hashes_and_cyclic_json_rejected():
    model = _train()["model"]
    model["weights"][0] += 0.1
    with pytest.raises(learned.LearnedRerankerError, match="WEIGHTS_SHA_MISMATCH"):
        learned.validate_model(model)
    model["weights_sha256"] = learned.canonical_sha256(model["weights"])
    with pytest.raises(learned.LearnedRerankerError, match="MODEL_SHA_MISMATCH"):
        learned.validate_model(model)
    model["loop"] = model
    with pytest.raises(learned.LearnedRerankerError, match="JSON_CYCLE"):
        learned.validate_model(model)


def test_nil_only_does_not_fabricate_a_ranking_or_nil_model():
    bundle = training_fixture()
    row = bundle[0]["rows"][0]
    row["assignment"].update(truth_kind="NIL", truth_label="__NIL__", binding_status="NOT_APPLICABLE",
                             matched_candidate_ids=[], gold_work_fingerprint=None)
    for exposure in row["exposures"]:
        exposure["polarity"] = "NEGATIVE"
    with pytest.raises(learned.LearnedRerankerError, match="NO_TRAINABLE_PAIRS"):
        _train(_reseal(bundle))


def test_nil_row_retained_in_train_denominator_and_does_not_optimize():
    one = _train()["model"]
    result = _train(training_fixture(include_nil=True))
    report = result["training_report"]
    assert report["train_rows"] == 2 and report["pair_rows"] == report["nil_rows"] == 1
    assert [row["status"] for row in report["rows"]] == ["USED_PAIRWISE", "NO_PAIR_NIL"]
    assert report["training_binding"]["label_grade_counts"] == {"SYNTHETIC_FIXTURE": 2}
    assert result["model"]["weights"] == one["weights"]


@pytest.mark.parametrize("config", [None, 1, [], "invalid"])
def test_malformed_model_config_raises_contract_error(config):
    model = _train()["model"]
    model["config"] = config
    with pytest.raises(learned.LearnedRerankerError, match="CONFIG_INVALID"):
        learned.validate_model(_model_seal(model))


def test_bool_coordinate_cannot_match_strict_integer_in_capture():
    bundle = training_fixture()
    capture = _capture(bundle)
    capture["binding"] = {**capture["binding"], "input_index": True}
    raw = _raw(capture)
    bundle[3][0]["capture_sha256"] = _sha(raw)
    bundle[2][_sha(raw)] = raw
    with pytest.raises(learned.LearnedRerankerError, match="PRESELECTION_CAPTURE_MISMATCH"):
        _train(bundle)


def test_source_backed_model_reference_remains_declared_model_reference():
    bundle = training_fixture()
    bundle[0]["data_kind"] = "SOURCE_BACKED"
    for source in bundle[0]["sources"]:
        source["rights_status"] = "REUSE_PERMITTED"
    for row in bundle[0]["rows"]:
        row["label_provenance"]["grade"] = "MODEL_REFERENCE"
        for mention in row["role_mentions"]:
            mention["provenance"]["grade"] = "MODEL_REFERENCE"
    result = _train(_reseal(bundle))
    assert result["model"]["data_kind"] == "SOURCE_BACKED"
    assert result["model"]["training_binding"]["label_grade_counts"] == {"MODEL_REFERENCE": 1}
    assert result["training_report"]["actual_performance_evaluated"] is False
    # This test changes declared metadata only, and does not establish real data.


@pytest.mark.parametrize("status", ["TRUNCATED", "UNKNOWN"])
def test_incomplete_generation_is_not_scored_as_complete(status):
    bundle = training_fixture()
    model = _train(bundle)["model"]
    bundle[3][0]["frozen_view"]["generation_status"] = status
    with pytest.raises(learned.LearnedRerankerError, match="GENERATION_NOT_COMPLETE"):
        learned.score_view(model, bundle[3][0]["frozen_view"])


def test_tie_keeps_input_order_not_id_as_feature_or_tiebreak():
    bundle = training_fixture()
    model = _train(bundle)["model"]
    view = deepcopy(bundle[3][0]["frozen_view"])
    twin = deepcopy(view["candidates"][0])
    view["candidates"][0]["candidate_id"] = "z-unseen"
    twin["candidate_id"] = "a-unseen"
    view["candidates"] = [view["candidates"][0], twin]
    scores = learned.score_view(model, view)
    assert [item["candidate_id"] for item in scores] == ["z-unseen", "a-unseen"]
    assert scores[0]["score"] == scores[1]["score"]
