"""학습에 배정하지 않은 실제 R2 입력에 고정 CAL 값을 소비하는 범위 시험."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from src.llm_batch.grounding import candidate_reranker_calibration as fit
from src.llm_batch.grounding import candidate_reranker_calibration_inference as inference
from src.llm_batch.grounding.candidate_reranker_inference_graph import build_inference_graph
from src.llm_batch.grounding.candidate_set_calibration_shadow import PROBABILITY_SCALE, _probability_masses
from tests.candidate_reranker_semantic_calibration_fixtures import build_semantic_calibration_fixture
from test_candidate_reranker_inference_graph import build_inference_graph_fixture, arguments


@pytest.fixture(scope="module")
def calibrated(tmp_path_factory):
    fixture = build_semantic_calibration_fixture(tmp_path_factory.mktemp("unseen-calibration"))
    artifact = fit.fit_temperature(fixture["calibration_events"],
        split_manifest=fixture["calibration_manifest"], policy=fixture["policy"])["artifact"]
    args = {"scorer_summary": fixture["scorer_summary"], "artifact": artifact.to_dict(),
        "calibration_manifest": fixture["calibration_manifest"].to_dict(), "policy": fixture["policy"].to_dict()}
    return fixture, args, inference.prepare_inference_calibration(**args)


@pytest.mark.parametrize("post_id", [99001, "99001"])
def test_unassigned_typed_posts_consume_actual_r2_semantic_nil_and_fixed_cal_without_io(calibrated, post_id, monkeypatch):
    fixture, args, observer = calibrated
    value = build_inference_graph_fixture(fixture["scorer"], post_id=post_id)
    graph = build_inference_graph(**arguments(value))
    before = deepcopy((args, graph, value["capture"]))
    assert str(post_id) not in {a.post_id for a in fixture["calibration_manifest"].assignments}
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("consumer file IO"))
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("consumer network"))
    monkeypatch.setattr(fit, "_solve", lambda *a, **k: pytest.fail("per-post optimizer"))
    monkeypatch.setattr(type(fixture["scorer"]), "score", lambda *a, **k: pytest.fail("core numerical replay belongs to runtime"))
    receipt = observer.apply(graph, **arguments(value))
    assert receipt["status"] == "TEMPERATURE_APPLIED_BOUND_INFERENCE", receipt
    assert type(receipt["post_id"]) is type(post_id) and receipt["post_id"] == post_id
    assert receipt["evaluation_split"] is None and receipt["truth_status"] == "UNJUDGED_NOT_ASSIGNED"
    assert receipt["semantic_input_sha256"] == value["capture"]["semantic_input"]["input_sha256"]
    probabilities = receipt["event_probabilities"]
    assert [p["label"] for p in probabilities] == graph["labels"]
    assert [p["probability_mass"] for p in probabilities] == list(_probability_masses(graph["raw_scores"], args["artifact"]["temperature"]))
    assert sum(p["probability_mass"] for p in probabilities) == PROBABILITY_SCALE
    assert probabilities[-1]["label"] == "__NIL__" and probabilities[-1]["probability"] == receipt["nil_probability"]
    assert receipt["score_provenance"] == "CAPTURE_STRUCTURAL_BINDING_RUNTIME_REPLAY_REQUIRED"
    assert all(receipt[k] is False for k in ("actual_quality_evaluated", "publication_authority", "public_apply", "central_db_write", "action_applied"))
    assert before == (args, graph, value["capture"])
    assert receipt == observer.apply(graph, **arguments(value))


@pytest.mark.parametrize("kwargs", [{"top_k": 1}, {"text": "비매칭글자"}])
def test_incomplete_or_empty_candidates_never_gain_nil_probability(calibrated, kwargs):
    fixture, _, observer = calibrated
    from src.llm_batch.grounding.candidate_retrieval_shadow import load_corpus_bytes
    from src.llm_batch.runtime.candidate_reranker import _source_view, observe_candidate_reranker_with_capture
    from src.llm_batch.runtime.candidate_semantics import CandidateSemanticsObserver, observe_candidate_semantics
    from test_candidate_reranker_inference_graph import sha
    value = build_inference_graph_fixture(fixture["scorer"])
    retrieval = load_corpus_bytes(value["corpus_snapshot"], expected_sha256=sha(value["corpus_snapshot"]),
                                 top_k=kwargs.get("top_k", 20))
    post = SimpleNamespace(post_id=99003, title=kwargs.get("text", "나는 합성 바다 기록을 리뷰한다."), content_blocks=[], comments=[])
    r2 = retrieval.observe(_source_view(post))
    semantics = CandidateSemanticsObserver()
    package = observe_candidate_semantics(semantics, post, r2, retrieval)
    observed = observe_candidate_reranker_with_capture(fixture["scorer"], post, r2, retrieval,
        semantic_package=package, semantic_observer=semantics)
    assert observed["capture"] is None
    assert observed["receipt"]["nil_probability"] is None
    receipt = observer.apply({}, capture=None, corpus_snapshot=value["corpus_snapshot"], source_payloads=value["source_payloads"])
    assert receipt["status"] == "NOT_AVAILABLE" and receipt["event_probabilities"] is None
    assert receipt["nil_probability"] is None and receipt["selected_label"] is None


@pytest.mark.parametrize("fault", ["corpus", "source", "graph_score", "post_id", "capture"])
def test_changed_evidence_has_no_probability(calibrated, fault):
    fixture, _, observer = calibrated
    value = build_inference_graph_fixture(fixture["scorer"])
    graph = build_inference_graph(**arguments(value))
    if fault == "corpus": value["corpus_snapshot"] += b" "
    elif fault == "source": value["source_payloads"][next(iter(value["source_payloads"]))] += b"!"
    elif fault == "graph_score": graph["raw_scores"][0] += 1
    elif fault == "post_id": graph["post_id"] = str(graph["post_id"])
    else: value["capture"]["capture_sha256"] = "0" * 64
    receipt = observer.apply(graph, **arguments(value))
    assert receipt["status"] == "NOT_AVAILABLE" and receipt["event_probabilities"] is None


@pytest.mark.parametrize("fault", ["model", "base", "train", "semantic", "temperature", "policy", "manifest", "v1"])
def test_preparation_rejects_wrong_model_cal_or_policy(calibrated, fault):
    _, args, _ = calibrated
    args = deepcopy(args)
    if fault in {"model", "base", "train", "semantic"}:
        key = {"model": "model_sha256", "base": "candidate_ranker_model_sha256",
               "train": "training_split_manifest_sha256", "semantic": "semantic_policy_sha256"}[fault]
        args["scorer_summary"][key] = "0" * 64
    elif fault == "temperature": args["artifact"]["temperature"] *= 2
    elif fault == "policy": args["policy"]["nil_min_probability"] = .1
    elif fault == "manifest": args["calibration_manifest"]["manifest_sha256"] = "0" * 64
    else: args["artifact"]["schema_version"] = "candidate_set_calibration_artifact_v1"
    with pytest.raises(ValueError):
        inference.prepare_inference_calibration(**args)


def test_prepared_consumer_is_detached_and_immutable(calibrated):
    _, _, observer = calibrated
    first = observer.summary()
    first["temperature"] = -1
    assert observer.summary()["temperature"] > 0
    with pytest.raises(FrozenInstanceError):
        observer._summary_json = b"{}"
