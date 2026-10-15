"""전체 CAL temperature 학습·증거 재판독·구형 FROZEN 소비의 합성 시험."""
from copy import deepcopy
import json
import math

import pytest

from src.llm_batch.grounding import candidate_reranker_calibration as learned
from src.llm_batch.grounding.candidate_reranker_calibration_data import CalibrationFitEvent
from src.llm_batch.grounding.candidate_set_calibration_shadow import (
    CalibrationArtifact, CalibrationEvaluationPolicy, CalibrationFitReceipt,
    build_calibration_shadow, calibration_artifact_from_dict,
)
from candidate_reranker_calibration_fixtures import build_calibration_fixture


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    return build_calibration_fixture(tmp_path_factory.mktemp("temperature-contract"))


def fit(bundle, events=None, **kwargs):
    return learned.fit_temperature(bundle["calibration_events"] if events is None else events,
        split_manifest=bundle["calibration_manifest"], policy=bundle["policy"], **kwargs)


@pytest.fixture(scope="module")
def fitted(bundle):
    return fit(bundle)


def changed_event(event, **changes):
    payload = event.to_dict()
    payload.pop("event_sha256")
    payload.update(changes)
    return CalibrationFitEvent.create(**payload)


def reseal_artifact(payload):
    payload = deepcopy(payload)
    receipt = payload["fit_receipt"]
    evidence = receipt["learning_evidence"]
    evidence["evidence_sha256"] = learned.canonical_sha256({k: v for k, v in evidence.items()
                                                          if k != "evidence_sha256"})
    receipt["receipt_sha256"] = learned.canonical_sha256({k: v for k, v in receipt.items()
                                                        if k != "receipt_sha256"})
    payload["artifact_sha256"] = learned.canonical_sha256({k: v for k, v in payload.items()
                                                         if k != "artifact_sha256"})
    return payload


def test_bounded_convex_solver_finds_analytic_interior_minimum():
    # P(high truth)=3/4 yields beta=log(3), independently of this solver.
    rows = [((0.0, 1.0), 1)] * 3 + [((0.0, 1.0), 0)]
    result = learned._solve(rows, learned._config(None))
    expected = math.log(3.0)
    assert result["beta"] == pytest.approx(expected, abs=1e-9)
    assert result["temperature"] == pytest.approx(1 / expected, abs=1e-9)
    assert result["nll_after"] == pytest.approx(-(3 * math.log(0.75) + math.log(0.25)) / 4)
    assert result["nll_after"] < result["nll_before"]
    assert result["status"].startswith("INTERIOR_")
    assert result["bracket"][0] <= expected + 1e-12
    assert result["bracket"][1] >= expected - 1e-12
    assert result["bracket"][1] - result["bracket"][0] <= 1e-10


@pytest.mark.parametrize("rows,status,beta", [
    ([((0.0, 1.0), 0)], "LOWER_BOUND_OPTIMUM", 0.01),
    ([((1.0, 0.0), 0)], "UPPER_BOUND_OPTIMUM", 100.0),
    ([((7.0, 7.0), 0), ((-6.0, -6.0), 1)], "FLAT_IDENTITY", 1.0),
])
def test_solver_boundaries_and_nonidentifiable_identity(rows, status, beta):
    result = learned._solve(rows, learned._config(None))
    assert result["status"] == status and result["beta"] == beta
    assert result["iterations"] == 0 and result["converged"] is True
    assert result["identifiable"] is (status != "FLAT_IDENTITY")
    assert result["nll_after"] <= result["nll_before"]


def test_solver_stable_large_logits_and_constant_shift():
    original = [((0, 1), 1)] * 3 + [((0, 1), 0)]
    shifted = [((9000, 9001), target) for _, target in original]
    assert learned._solve(original, learned._config(None)) == learned._solve(shifted, learned._config(None))
    result = learned._solve([((-10000, 10000), 0), ((-10000, 10000), 1)], learned._config(None))
    assert math.isfinite(result["nll_after"]) and result["status"] == "LOWER_BOUND_OPTIMUM"


@pytest.mark.parametrize("config", [
    {"beta_min": 0}, {"beta_min": 2}, {"beta_max": 0.5}, {"beta_max": 101},
    {"beta_min": 1, "beta_max": 1}, {"max_iterations": True}, {"max_iterations": 257},
    {"max_iterations": 0}, {"beta_tolerance": float("nan")}, {"beta_tolerance": 1e-20},
    {"unknown": 1}, None,
])
def test_config_and_nonconvergence_are_explicit(config):
    if config is None:
        rows = [((0, 1), 1)] * 3 + [((0, 1), 0)]
        with pytest.raises(ValueError, match="NOT_CONVERGED"):
            learned._solve(rows, learned._config({"max_iterations": 1}))
    else:
        with pytest.raises(ValueError):
            learned._config(config)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), True, 10001, 10 ** 500])
def test_nonfinite_or_unbounded_scores_cannot_enter_optimizer(score):
    with pytest.raises(ValueError):
        learned._solve([((score, 0), 0)], learned._config(None))


def test_actual_cal_fit_roundtrip_and_existing_frozen_consumer(bundle, fitted, tmp_path):
    artifact, report = fitted["artifact"], fitted["fit_report"]
    assert artifact.schema_version == learned.ARTIFACT_SCHEMA
    assert artifact.fit_receipt.schema_version == learned.RECEIPT_SCHEMA
    assert report["optimizer_executed"] is True and report["data_kind"] == "SYNTHETIC_FIXTURE"
    assert report["publication_authority"] is False and report["actual_performance_evaluated"] is False
    assert report["counts"]["truth"] == {"CANDIDATE": 1, "NIL": 1}
    assert report["solver"]["nll_after"] <= report["solver"]["nll_before"] + 1e-12
    target = tmp_path / "calibration.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(artifact.to_dict(), stream, ensure_ascii=False, allow_nan=False)
    restored = calibration_artifact_from_dict(json.loads(target.read_text(encoding="utf-8")))
    assert restored.to_dict() == artifact.to_dict()
    restored.validate_against(bundle["calibration_manifest"], bundle["policy"])
    for example_id, vector in bundle["frozen_vectors"].items():
        shadow = build_calibration_shadow(bundle["frozen_base_shadows"][example_id], vector, restored,
            bundle["policy"], split_manifest=bundle["calibration_manifest"],
            assignment=bundle["frozen_assignments"][example_id])
        assert shadow.probability_status == "CALIBRATED_SHADOW_BOUND"
        assert sum(item.probability_mass for item in shadow.event_probabilities) == 1_000_000
        assert shadow.action_applied is False and shadow.calibration_artifact_sha256 == restored.artifact_sha256


def test_determinism_and_source_model_immutability(bundle, fitted):
    watched = {key: learned.canonical_sha256(bundle[key]) for key in ("model", "training_manifest")}
    events = [e.to_dict() for e in bundle["calibration_events"]]
    replay = fit(bundle)
    assert replay["artifact"].to_dict() == fitted["artifact"].to_dict()
    assert replay["fit_report"] == fitted["fit_report"]
    assert events == [e.to_dict() for e in bundle["calibration_events"]]
    assert watched == {key: learned.canonical_sha256(bundle[key]) for key in watched}
    learned.validate_fit_evidence(fitted["artifact"].fit_receipt.learning_evidence,
        fitted["artifact"].fit_receipt, artifact=fitted["artifact"])


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "reverse"])
def test_whole_external_cal_denominator_and_order_required(bundle, mutation):
    events = list(bundle["calibration_events"])
    if mutation == "drop":
        events.pop()
    elif mutation == "duplicate":
        events.append(events[0])
    else:
        events.reverse()
    with pytest.raises(ValueError):
        fit(bundle, events)


@pytest.mark.parametrize("field", ["model_sha256", "base_model_sha256", "training_split_manifest_sha256",
    "scorer_fingerprint", "calibration_manifest_sha256", "candidate_set_fingerprint", "post_id"])
def test_resealed_event_binding_conflicts_are_rejected(bundle, field):
    events = list(bundle["calibration_events"])
    events[0] = changed_event(events[0], **{field: "different-post" if field == "post_id" else "d" * 64})
    with pytest.raises(ValueError):
        fit(bundle, events)


def test_provenance_and_truth_cannot_be_relabelled_after_bridge(bundle):
    events = list(bundle["calibration_events"])
    candidate_index = next(i for i, event in enumerate(events) if event.truth_kind == "CANDIDATE")
    original = events[candidate_index]
    events[candidate_index] = changed_event(original, truth_kind="NIL", truth_label="__NIL__")
    with pytest.raises(ValueError, match="ASSIGNMENT"):
        fit(bundle, events)
    events[candidate_index] = changed_event(original,
        label_provenance={**dict(original.label_provenance), "artifact_sha256": "e" * 64})
    with pytest.raises(ValueError, match="PROVENANCE"):
        fit(bundle, events)


@pytest.mark.parametrize("field", ["min_dev_rows", "min_dev_per_truth_class",
    "min_calibration_rows", "min_calibration_per_truth_class"])
def test_existing_policy_minimums_are_not_relaxed(bundle, field):
    values = bundle["policy"].payload_without_policy_sha256()
    values[field] = 100
    policy = CalibrationEvaluationPolicy.create(**values)
    with pytest.raises(ValueError, match="minimum"):
        learned.fit_temperature(bundle["calibration_events"],
            split_manifest=bundle["calibration_manifest"], policy=policy)


@pytest.mark.parametrize("field", ["temperature", "nll_after", "iterations", "bracket", "status"])
def test_resealed_solver_results_cannot_replace_deterministic_fit(fitted, field):
    payload = fitted["artifact"].to_dict()
    solver = payload["fit_receipt"]["learning_evidence"]["solver"]
    if field == "temperature":
        value = solver[field] * 1.5
        solver[field] = value
        payload["temperature"] = payload["fit_receipt"]["temperature"] = value
    elif field == "bracket":
        solver[field] = [0.02, 99.0]
    elif field == "status":
        solver[field] = "CLAIMED_OPTIMUM"
    else:
        solver[field] += 1
    with pytest.raises(ValueError, match="REPLAY"):
        calibration_artifact_from_dict(reseal_artifact(payload))


@pytest.mark.parametrize("field", ["policy_sha256", "split_manifest_sha256",
    "calibration_split_fingerprint", "frozen_holdout_fingerprint"])
def test_standalone_loader_binds_outer_artifact_to_embedded_context(fitted, field):
    payload = fitted["artifact"].to_dict()
    payload[field] = "f" * 64
    with pytest.raises(ValueError):
        calibration_artifact_from_dict(reseal_artifact(payload))


def test_explicit_external_context_and_legacy_v1_remain_distinct(bundle, fitted):
    artifact = fitted["artifact"]
    values = bundle["policy"].payload_without_policy_sha256()
    values["nil_min_probability"] = 0.012345
    different = CalibrationEvaluationPolicy.create(**values)
    with pytest.raises(ValueError, match="EXTERNAL_POLICY"):
        learned.validate_fit_evidence(artifact.fit_receipt.learning_evidence, artifact.fit_receipt,
                                     policy=different)
    receipt_payload = artifact.fit_receipt.payload_without_receipt_sha256()
    receipt_payload.pop("learning_evidence")
    receipt_payload["schema_version"] = "candidate_set_calibration_fit_receipt_v1"
    old_receipt = CalibrationFitReceipt.create(**receipt_payload)
    outer = artifact.payload_without_artifact_sha256()
    outer.update(schema_version="candidate_set_calibration_artifact_v1", fit_receipt=old_receipt)
    old = CalibrationArtifact.create(**outer)
    assert "learning_evidence" not in old.to_dict()["fit_receipt"]
    assert calibration_artifact_from_dict(old.to_dict()).to_dict() == old.to_dict()
    with pytest.raises(ValueError, match="V2_FIT_RECEIPT"):
        learned.validate_fit_evidence({}, old_receipt)
