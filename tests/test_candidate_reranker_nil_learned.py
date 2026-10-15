"""합성 TRAIN의 후보/NIL 학습·고정 base·원문 결속을 검증한다."""
from copy import deepcopy
import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_batch.grounding import candidate_reranker_learned as pairwise
from llm_batch.grounding import candidate_reranker_nil_learned as nil
from llm_batch.grounding import reranker_training_split as split
from test_candidate_reranker_learned import training_fixture as _pairwise_fixture
from test_candidate_reranker_learned import _capture


def training_fixture():
    """Stable public factory: explicit CANDIDATE and NIL TRAIN, other splits intact.

    Returns (manifest, source_payloads, evidence_payloads, examples).
    Synthetic labels exercise binding only; they are not human semantic gold.
    """
    return _pairwise_fixture(include_nil=True)


def _train(bundle=None, *, config=None):
    manifest, sources, evidence, examples = training_fixture() if bundle is None else bundle
    return nil.train_model(manifest, source_payloads=sources, evidence_payloads=evidence,
        examples=examples, config={"base": {"epochs": 8}, "nil_head": {"epochs": 16}} if config is None else config)


def _base(bundle):
    return pairwise.train_model(bundle[0], source_payloads=bundle[1], evidence_payloads=bundle[2],
        examples=bundle[3], config={"epochs": 8})["model"]


def _head(base, bundle):
    return nil.train_nil_head(base, bundle[0], source_payloads=bundle[1], evidence_payloads=bundle[2],
        examples=bundle[3], config={"epochs": 16})


def _seal_model(model):
    model["model_sha256"] = nil.canonical_sha256({k: v for k, v in model.items() if k != "model_sha256"})
    return model


def _seal_split(bundle):
    bundle[0]["manifest_sha256"] = split.seal_manifest(bundle[0])["manifest_sha256"]
    return bundle


def test_joint_event_loss_learns_nil_parameters_only_and_keeps_probabilities_unavailable():
    bundle = training_fixture()
    before = deepcopy(bundle)
    base = _base(bundle)
    with patch.object(Path, "open", side_effect=AssertionError("pure trainer must not open files")):
        result = _train(bundle)
    model, report = result["model"], result["training_report"]
    assert bundle == before and model["base_model"] == base
    assert model["base_model_sha256"] == nil.canonical_sha256(base)
    assert report["base_parameters_updated"] is False and report["parameters_changed"] is True
    assert report["final_loss"] < report["initial_loss"]
    assert report["optimization_split"] == "TRAIN"
    assert report["train_rows"] == 2 and report["candidate_rows"] == report["nil_rows"] == 1
    assert report["training_binding"]["truth_counts"] == {"CANDIDATE": 1, "NIL": 1}
    assert {r["status"] for r in report["rows"]} == {"USED_NIL_SOFTMAX"}
    assert report["base_training_report"]["nil_rows"] == 1
    assert model["data_kind"] == "SYNTHETIC_FIXTURE" and model["backend"] == nil.BACKEND
    assert model["feature_contract"] == nil.FEATURE_CONTRACT and len(model["weights"]) == 24
    assert model["publication_authority"] is report["actual_performance_evaluated"] is False
    assert report["nil_probability"] is report["selected_label"] is None
    assert report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert report["probability_status"] == "NOT_AVAILABLE_UNCALIBRATED"
    assert "scores" not in model and "labels" not in model


def test_deterministic_training_json_readback_and_supplied_base_equivalence():
    bundle = training_fixture()
    result = _train(bundle)
    assert result == _train(bundle)
    assert _head(_base(bundle), bundle)["model"] == result["model"]
    loaded = nil.validate_model(json.loads(json.dumps(result["model"], ensure_ascii=False)))
    assert loaded == result["model"] and loaded is not result["model"]
    loaded["base_model"]["weights"][0] += 1
    assert loaded != result["model"]
    report = deepcopy(result["training_report"])
    digest = report.pop("report_sha256")
    assert nil.canonical_sha256(report) == digest


def test_scores_preserve_fixed_order_and_base_scores_with_unseen_ids_and_no_id_features():
    bundle = training_fixture()
    model = _train(bundle)["model"]
    view = deepcopy(bundle[3][0]["frozen_view"])
    expected = {r["candidate_id"]: r["score"] for r in pairwise.score_view(model["base_model"], view)}
    first = nil.score_event_logits(model, view)
    assert first["labels"] == [c["candidate_id"] for c in view["candidates"]] + ["__NIL__"]
    assert first["raw_scores"] == [expected[c["candidate_id"]] for c in view["candidates"]] + [first["nil_score"]]
    assert first["candidate_scores"] == [{"candidate_id": c["candidate_id"], "score": expected[c["candidate_id"]]} for c in view["candidates"]]
    assert first["nil_probability"] is first["selected_label"] is None
    assert first["publication_authority"] is first["public_apply"] is first["central_db_write"] is False
    assert all(math.isfinite(s) for s in first["raw_scores"])
    original = deepcopy(view)
    view["post_id"] = view["source_view"]["post_id"] = "unseen-post"
    for i, c in enumerate(view["candidates"]): c["candidate_id"] = f"unseen-{i}"
    renamed = nil.score_event_logits(model, view)
    assert renamed["raw_scores"] == first["raw_scores"]
    assert renamed["feature_sha256"] == first["feature_sha256"]
    view["candidates"].reverse()
    reversed_event = nil.score_event_logits(model, view)
    assert reversed_event["raw_scores"] == [*reversed(first["raw_scores"][:-1]), first["nil_score"]]
    assert reversed_event["feature_sha256"] == first["feature_sha256"]
    assert nil.score_event_logits(model, original) == first


@pytest.mark.parametrize("fault", ["empty", "truncated", "unknown", "empty_query", "ineligible"])
def test_single_candidate_supported_but_operational_absence_or_ineligibility_is_not_nil(fault):
    bundle = training_fixture()
    model = _train(bundle)["model"]
    view = deepcopy(bundle[3][0]["frozen_view"])
    view["candidates"] = view["candidates"][:1]
    event = nil.score_event_logits(model, view)
    assert len(event["labels"]) == 2 and event["labels"][-1] == nil.NIL_LABEL
    assert event["nil_probability"] is None
    if fault == "empty": view["candidates"] = []
    if fault == "truncated": view["generation_status"] = "TRUNCATED"
    if fault == "unknown": view["generation_status"] = "UNKNOWN"
    if fault == "empty_query":
        view["source_view"]["fragments"] = []
        view["candidates"][0]["role_observations"] = []
    if fault == "ineligible": view["candidates"][0].update(event_eligible=False, identity_conflict=True)
    with pytest.raises(ValueError): nil.score_event_logits(model, view)


def test_both_train_truth_classes_are_required_and_candidate_missing_is_not_relabeled_nil():
    one_class = _pairwise_fixture()
    with pytest.raises(ValueError, match="BOTH_TRAIN_TRUTH_CLASSES_REQUIRED"):
        _head(_base(one_class), one_class)
    bundle = training_fixture()
    base = _base(bundle)
    row = bundle[0]["rows"][0]
    row["assignment"].update(binding_status="MISSING", truth_label=None, matched_candidate_ids=[])
    _seal_split(bundle)
    with pytest.raises(ValueError, match="FULL_SPLIT_NOT_VALID"):
        _head(base, bundle)
    assert row["assignment"]["truth_kind"] == "CANDIDATE"


@pytest.mark.parametrize("fault", ["split", "capture", "source_bytes", "unjudged", "nil_positive"])
def test_base_split_original_bytes_capture_and_truth_contradictions_fail_closed(fault):
    bundle = training_fixture()
    base = _base(bundle)
    if fault == "split":
        bundle[0]["rows"][1]["label_provenance"]["reviewer"] = "another declared reviewer"
        _seal_split(bundle)
    if fault == "capture":
        bundle[3][0]["frozen_view"]["candidates"][0]["role_observations"][0]["role"] = "MENTIONED"
        _capture(bundle)
    if fault == "source_bytes": bundle[1][next(iter(bundle[1]))] += b"changed"
    if fault == "unjudged":
        bundle[0]["rows"][-1]["assignment"].update(truth_kind="UNJUDGED", truth_label=None)
        _seal_split(bundle)
    if fault == "nil_positive":
        bundle[0]["rows"][-1]["exposures"][0]["polarity"] = "POSITIVE"
        _seal_split(bundle)
    with pytest.raises(ValueError): _head(base, bundle)


def test_nontrain_label_and_annotation_changes_do_not_train_nil_weights():
    bundle = training_fixture()
    original = _train(bundle)
    for row in bundle[0]["rows"]:
        if row["assignment"]["split"] == "TRAIN": continue
        row["exposures"][0]["polarity"], row["exposures"][1]["polarity"] = "NEGATIVE", "POSITIVE"
        assignment = row["assignment"]
        assignment["truth_label"] = row["exposures"][1]["candidate_id"]
        assignment["matched_candidate_ids"] = [assignment["truth_label"]]
        assignment["gold_work_fingerprint"] = split.canonical_sha256(row["exposures"][1]["work_id"])
        for mention in row["role_mentions"]: mention["roles"] = ["PREVIOUS"]
    changed = _train(_seal_split(bundle))
    assert original["model"]["weights"] == changed["model"]["weights"]
    assert original["model"]["base_model"]["weights"] == changed["model"]["base_model"]["weights"]
    assert original["model"]["training_binding"]["split_manifest_sha256"] != changed["model"]["training_binding"]["split_manifest_sha256"]


@pytest.mark.parametrize("fault", ["weights", "base", "split", "truth_count", "config", "feature", "authority", "extra", "digest"])
def test_resealed_model_tampering_is_rejected(fault):
    model = deepcopy(_train()["model"])
    if fault == "weights":
        model["weights"][0] = True
        model["weights_sha256"] = nil.canonical_sha256(model["weights"])
    if fault == "base": model["base_model"]["weights"][0] += 1
    if fault == "split": model["training_binding"]["split_manifest_sha256"] = "0" * 64
    if fault == "truth_count": model["training_binding"]["truth_counts"] = {"CANDIDATE": 2, "NIL": 0}
    if fault == "config": model["config"] = None
    if fault == "feature": model["feature_contract"]["excluded"] = []
    if fault == "authority": model["publication_authority"] = True
    if fault == "extra": model["nil_probability"] = 0.9
    _seal_model(model)
    if fault == "digest": model["model_sha256"] = "0" * 64
    with pytest.raises(ValueError): nil.validate_model(model)


@pytest.mark.parametrize("config", [{"epochs": 8}, {"nil_head": {"epochs": True}},
    {"nil_head": {"epochs": 201}}, {"nil_head": {"learning_rate": float("inf")}},
    {"base": {"unknown": 1}}, {"nil_head": {"l2": -1}}])
def test_configuration_rejects_unbounded_unknown_and_nonfinite_values(config):
    with pytest.raises(ValueError): _train(config=config)


def test_finite_large_base_logits_use_stable_loss_and_never_become_probabilities():
    bundle = training_fixture()
    base = _base(bundle)
    # A declared bounded model is sufficient here; this is a numerical contract
    # fixture, not a claim that these weights were learned from the source.
    base["weights"] = [100.0] * len(base["weights"])
    base["weights_sha256"] = nil.canonical_sha256(base["weights"])
    _seal_model(base)
    result = _head(base, bundle)
    assert math.isfinite(result["training_report"]["final_loss"])
    event = nil.score_event_logits(result["model"], bundle[3][0]["frozen_view"])
    assert all(math.isfinite(v) for v in event["raw_scores"])
    assert event["nil_probability"] is None and event["selected_label"] is None
