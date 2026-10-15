"""새 입력의 실제 R2/NIL/CAL 소비·점수 재생·현재 행 결속·저장 실패 격리."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.llm_batch.runtime import candidate_inference as runtime
from tests.candidate_inference_fixtures import build_candidate_inference_fixture, raw, sha


@pytest.fixture(scope="module")
def fixture(tmp_path_factory):
    return build_candidate_inference_fixture(tmp_path_factory.mktemp("general-inference-runtime"))


def binding(row):
    return {"run_id": "inference-run", "input_index": 1, "post_id": row["post"].post_id,
        "attempt_id": "inference-attempt", "publication_scope_id": "inference-scope"}


def private(row):
    return SimpleNamespace(_candidate_inference=deepcopy(row["package"]),
        _candidate_reranker_capture=deepcopy(row["capture"]),
        _candidate_reranker_shadow=deepcopy(row["reranker_receipt"]),
        _candidate_reranker_semantics=deepcopy(row["semantic_package"]))


def export(fixture, row, result, tmp_path, **kwargs):
    params = {"binding": binding(row), "output_dir": tmp_path, "input_snapshot_sha256": "a" * 64,
        "current_post": row["post"], "retrieval_observer": fixture["retrieval_observer"],
        "semantic_observer": fixture["semantic_observer"]}
    params.update(kwargs)
    return runtime.export_candidate_inference_fields(result, fixture["observer"], **params)


def test_off_is_lazy_even_with_invalid_unused_paths(monkeypatch):
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("OFF I/O"))
    scorer = SimpleNamespace(summary=lambda: pytest.fail("OFF scorer"))
    settings = runtime.resolve_candidate_inference_settings(SimpleNamespace(candidate_inference="OFF"),
        {"EXPERT_INFERENCE_BUNDLE": "https://invalid", "EXPERT_INFERENCE_BUNDLE_SHA256": "bad"})
    assert runtime.prepare_candidate_inference(settings, scorer) is None
    assert runtime.observe_candidate_inference(None, None, None, None) is None
    assert runtime.candidate_inference_policy_fields(None) == {}
    assert runtime.export_candidate_inference_fields(None, None, binding=None, output_dir=None,
        input_snapshot_sha256=None, current_post=None, retrieval_observer=None) == {}


def test_settings_precedence_and_explicit_dependencies():
    env = {"EXPERT_CANDIDATE_INFERENCE": "SHADOW", "EXPERT_INFERENCE_BUNDLE": "declared.json",
        "EXPERT_INFERENCE_BUNDLE_SHA256": "a" * 64, "EXPERT_CANDIDATE_RERANKER": "SHADOW"}
    active = runtime.resolve_candidate_inference_settings(SimpleNamespace(candidate_retrieval="SHADOW"), env)
    assert active["mode"] == "SHADOW" and set(active["sources"].values()) == {"ENVIRONMENT"}
    assert runtime.resolve_candidate_inference_settings(SimpleNamespace(candidate_inference="OFF"), env)["mode"] == "OFF"
    for args in (SimpleNamespace(candidate_inference=True), SimpleNamespace(candidate_inference="shadow"),
                 SimpleNamespace(candidate_retrieval="OFF"), SimpleNamespace(candidate_retrieval="SHADOW", candidate_reranker="OFF")):
        with pytest.raises(ValueError):
            runtime.resolve_candidate_inference_settings(args, env)


def test_new_unassigned_posts_use_fixed_fit_without_training_io_or_input_mutation(fixture, monkeypatch):
    from src.llm_batch.grounding import candidate_reranker_calibration as fit
    from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
    from src.llm_batch.grounding import candidate_reranker_learned as base
    monkeypatch.setattr(fit, "fit_temperature", lambda *a, **k: pytest.fail("inference fit"))
    monkeypatch.setattr(nil, "train_model", lambda *a, **k: pytest.fail("inference NIL train"))
    monkeypatch.setattr(base, "train_model", lambda *a, **k: pytest.fail("inference train"))
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("observe I/O"))
    for row in fixture["rows"]:
        before = deepcopy(row)
        result = fixture["observer"].observe(row["post"], row["capture"], row["reranker_receipt"])
        assert result == row["package"] and row == before
        value = result["inference"]
        assert value["status"] == "TEMPERATURE_APPLIED_BOUND_INFERENCE"
        assert value["evaluation_split"] is None and value["truth_status"] == "UNJUDGED_NOT_ASSIGNED"
        assert value["actual_quality_evaluated"] is False and value["action_applied"] is False
        probabilities = value["event_probabilities"]
        assert sum(x["probability_mass"] for x in probabilities) == probabilities[0]["probability_scale"]
        assert probabilities[-1]["label"] == "__NIL__"
        assert row["reranker_receipt"]["nil_probability"] is None
    copy = fixture["observer"].summary()
    copy["status"] = "forged"
    assert fixture["observer"].summary()["status"] == "AVAILABLE"
    with pytest.raises(FrozenInstanceError):
        fixture["observer"]._corpus_snapshot = b"changed"


def test_resealed_structurally_valid_forged_logits_fail_actual_model_replay(fixture):
    from src.llm_batch.grounding.candidate_reranker_capture import build_capture, validate_capture, capture_semantic_payloads
    row = deepcopy(fixture["rows"][0])
    receipt = row["reranker_receipt"]
    receipt["nil_score"] = receipt["event_logits"][-1]["score"] = 777.0
    receipt["receipt_sha256"] = sha(raw({k:v for k,v in receipt.items() if k not in {"latency_ms", "binding", "receipt_sha256"}}))
    prior = row["capture"]
    forged = build_capture(prior["frozen_view"], receipt, prior["retrieval_receipt"], prior["scorer_summary"],
        semantic_input=prior["semantic_input"], evidence_payloads=capture_semantic_payloads(prior))
    assert validate_capture(forged) == forged
    result = fixture["observer"].observe(row["post"], forged, receipt)
    assert result["status"] == "NOT_AVAILABLE"
    assert result["reason_codes"] == ["ACTUAL_SCORE_REPLAY_MISMATCH"] and result["inference"] is None


@pytest.mark.parametrize("fault", ["source", "post_type", "missing_capture", "missing_receipt", "model"])
def test_changed_capture_or_source_is_not_assigned_a_probability(fixture, fault):
    row = deepcopy(fixture["rows"][0])
    if fault == "source": row["post"].title += " 변경"
    elif fault == "post_type": row["post"] = SimpleNamespace(post_id=str(row["post"].post_id))
    elif fault == "missing_capture": row["capture"] = None
    elif fault == "missing_receipt": row["reranker_receipt"] = None
    else: row["capture"]["scorer_summary"]["model_sha256"] = "0" * 64
    output = fixture["observer"].observe(row["post"], row["capture"], row["reranker_receipt"])
    assert output["status"] == "NOT_AVAILABLE" and output["inference"] is None


def test_atomic_saved_capture_matches_current_attempt_graph_and_raw_bytes(fixture, tmp_path):
    row = fixture["rows"][0]
    result = private(row)
    before = deepcopy(result.__dict__)
    fields = export(fixture, row, result, tmp_path)
    value, ref = fields["candidate_reranker_inference"], fields["candidate_inference_capture"]
    assert value["status"] == "TEMPERATURE_APPLIED_BOUND_INFERENCE", value
    assert value["score_replay_verified"] is True and ref["status"] == "SAVED"
    assert value["binding"] == {**binding(row), "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    stored_raw = (tmp_path / ref["artifact"]["path"]).read_bytes()
    assert len(stored_raw) == ref["artifact"]["bytes"] and sha(stored_raw) == ref["artifact"]["sha256"]
    stored = json.loads(stored_raw)
    assert stored["capture"] == row["capture"] and stored["graph"] == row["graph"]
    assert stored["inference"] == value["inference"] and result.__dict__ == before
    assert export(fixture, row, result, tmp_path) == fields
    assert len(list(tmp_path.rglob("*.json"))) == 1


@pytest.mark.parametrize("fault", ["current_source", "r2", "semantic", "raw", "probability", "wrong_post", "snapshot"])
def test_export_independently_rechecks_current_context_and_untrusted_package(fixture, tmp_path, fault):
    row = fixture["rows"][0]
    result = private(row)
    kwargs = {}
    if fault == "current_source":
        post = deepcopy(row["post"]); post.title += " 변경"; kwargs["current_post"] = post
    elif fault == "r2":
        kwargs["retrieval_observer"] = SimpleNamespace(observe=lambda source: {"bad": True}, summary=lambda: {})
    elif fault == "semantic": result._candidate_reranker_semantics = None
    elif fault == "raw": result._candidate_reranker_shadow["nil_score"] = 100.0
    elif fault == "probability":
        result._candidate_inference["inference"]["nil_probability"] = 1.0
        result._candidate_inference["package_sha256"] = sha(raw({k:v for k,v in result._candidate_inference.items() if k != "package_sha256"}))
    elif fault == "wrong_post": kwargs["binding"] = {**binding(row), "post_id": fixture["rows"][1]["post"].post_id}
    else: kwargs["input_snapshot_sha256"] = "not-a-sha"
    fields = export(fixture, row, result, tmp_path, **kwargs)
    assert fields["candidate_reranker_inference"]["status"] == "NOT_AVAILABLE"
    assert fields["candidate_reranker_inference"]["inference"] is None
    assert fields["candidate_inference_capture"]["artifact"] is None and not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize("failure", ["partial_write", "readback", "conflicting_destination"])
def test_storage_failure_never_exposes_probability_or_partial_final_reference(fixture, tmp_path, monkeypatch, failure):
    from tools import run_candidate_reranker_training as local
    from tools import run_candidate_reranker_calibration as cli
    original_read, original_write = local._read, local._write
    if failure == "partial_write":
        def partial(path, value):
            with path.open("xb") as stream: stream.write(b"{")
            raise OSError("short write")
        monkeypatch.setattr(local, "_write", partial)
    elif failure == "readback":
        monkeypatch.setattr(local, "_read", lambda path, limit: b"{}" if path.suffix == ".pending" else original_read(path, limit))
    else:
        def conflict(pending, target):
            with target.open("xb") as stream: stream.write(b"original destination")
            raise FileExistsError(target)
        monkeypatch.setattr(cli, "_rename_noreplace", conflict)
    fields = export(fixture, fixture["rows"][0], private(fixture["rows"][0]), tmp_path)
    assert fields["candidate_reranker_inference"]["status"] == "NOT_AVAILABLE"
    assert fields["candidate_reranker_inference"]["inference"] is None
    assert fields["candidate_inference_capture"]["artifact"] is None
    if failure == "conflicting_destination":
        assert next(tmp_path.rglob("*.json")).read_bytes() == b"original destination"
    else:
        assert not list(tmp_path.rglob("*.json"))


def test_missing_and_unexecuted_observations_are_distinct(fixture, tmp_path):
    row = fixture["rows"][0]
    absent = export(fixture, row, SimpleNamespace(), tmp_path)
    skipped = export(fixture, row, None, tmp_path)
    assert absent["candidate_reranker_inference"]["status"] == "NOT_AVAILABLE"
    assert skipped["candidate_reranker_inference"]["status"] == "NOT_EXECUTED"
    assert skipped["candidate_inference_capture"]["status"] == "NOT_EXECUTED"
    assert skipped["candidate_reranker_inference"]["inference"] is None


@pytest.mark.parametrize("case", ["EMPTY", "TRUNCATED"])
def test_unconsumed_semantic_terminal_without_capture_stays_unavailable(fixture, tmp_path, case):
    from src.llm_batch.domain.models import PostInput
    from src.llm_batch.grounding.candidate_retrieval_shadow import load_corpus_bytes
    from src.llm_batch.runtime.candidate_reranker import _source_view, observe_candidate_reranker_with_capture
    from src.llm_batch.runtime.candidate_semantics import observe_candidate_semantics
    retrieval = load_corpus_bytes(fixture["corpus_snapshot"], expected_sha256=fixture["corpus_sha256"],
                                  top_k=1 if case == "TRUNCATED" else 20)
    text = "독립된비매칭원문" if case == "EMPTY" else fixture["rows"][0]["post"].title
    post = PostInput(post_id=65000, title=text, content_blocks=[], comments=[])
    r2 = retrieval.observe(_source_view(post))
    semantic = observe_candidate_semantics(fixture["semantic_observer"], post, r2, retrieval)
    observed = observe_candidate_reranker_with_capture(fixture["scorer"], post, r2, retrieval,
        semantic_package=semantic, semantic_observer=fixture["semantic_observer"])
    assert observed["capture"] is None
    receipt = observed["receipt"]
    assert receipt["status"] == ("EMPTY_CANDIDATE_SET" if case == "EMPTY" else "NOT_SCORED_GENERATION_TRUNCATED")
    assert receipt["semantic_consumption"]["status"] == "NOT_CONSUMED"
    assert receipt["nil_probability"] is None and receipt["nil_score"] is None and receipt["event_logits"] == []
    package = fixture["observer"].observe(post, observed["capture"], receipt)
    assert package["status"] == "NOT_AVAILABLE" and package["inference"] is None and package["graph"] is None
    result = SimpleNamespace(_candidate_reranker_capture=None, _candidate_reranker_shadow=receipt,
        _candidate_reranker_semantics=semantic, _candidate_inference=package)
    row = {"post": post}
    fields = export(fixture, row, result, tmp_path, retrieval_observer=retrieval)
    assert fields["candidate_reranker_inference"]["status"] == "NOT_AVAILABLE"
    assert fields["candidate_reranker_inference"]["inference"] is None
    assert fields["candidate_inference_capture"]["artifact"] is None
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize("bad", [None, [], {"post_id": True}, {"post_id": object()}])
def test_invalid_binding_fallback_is_serializable_and_does_not_raise(fixture, tmp_path, bad):
    result = export(fixture, fixture["rows"][0], None, tmp_path, binding=bad)
    assert result["candidate_reranker_inference"]["status"] == "NOT_AVAILABLE"
    raw(result)
