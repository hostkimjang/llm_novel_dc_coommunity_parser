"""CAL 자료형의 유한값·자체 SHA·정답 출처·고정 모델/전체 집합 계약 시험."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json

import pytest

from src.llm_batch.grounding import candidate_reranker_calibration_data as data


def event(**changes):
    fields = {name: "a" * 64 for name in (
        "training_split_manifest_sha256", "calibration_manifest_sha256", "scorer_fingerprint",
        "scorer_summary_sha256", "model_sha256", "base_model_sha256", "source_binding_sha256",
        "raw_receipt_sha256", "candidate_set_fingerprint", "publication_input_fingerprint",
        "generation_proof_fingerprint", "retrieval_state_fingerprint", "feature_fingerprint")}
    fields.update(example_id="synthetic-example-1", post_id="synthetic-post-1",
        labels=["cand_" + "b" * 64, "__NIL__"], raw_scores=[-2, 3], truth_kind="CANDIDATE",
        truth_label="cand_" + "b" * 64, data_kind="SYNTHETIC_FIXTURE",
        label_provenance={"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": "c" * 64,
            "reviewer": "합성 작성자", "scope": "WORK_IDENTITY"})
    fields.update(changes)
    return data.CalibrationFitEvent.create(**fields)


def test_roundtrip_seal_copy_and_scores_do_not_define_truth():
    value = event()
    serialized = json.loads(json.dumps(value.to_dict(), ensure_ascii=False))
    loaded = data.CalibrationFitEvent.from_dict(serialized)
    assert loaded == value and loaded.raw_scores == (-2.0, 3.0)
    assert loaded.truth_label != loaded.labels[loaded.raw_scores.index(max(loaded.raw_scores))]
    assert loaded.event_sha256 == data.canonical_sha256({k: v for k, v in serialized.items() if k != "event_sha256"})
    serialized["label_provenance"]["reviewer"] = "변경된 작성자"
    serialized["labels"][0] = "changed"
    assert value.label_provenance["reviewer"] == "합성 작성자"
    assert deepcopy(value) is value
    with pytest.raises(TypeError):
        value.label_provenance["grade"] = "HUMAN_GOLD"
    with pytest.raises(FrozenInstanceError):
        value.model_sha256 = "d" * 64


@pytest.mark.parametrize("scores", [[True, 0], [0, False], [0, float("nan")], [float("inf"), 0],
    [0, -float("inf")], ["1", 2], [None, 2], [10**1000, 0]])
def test_bool_and_nonfinite_are_not_raw_scores(scores):
    with pytest.raises(data.CalibrationDataError, match="FINITE_RAW_SCORE_REQUIRED"):
        event(raw_scores=scores)


@pytest.mark.parametrize("mutation", ["one_nil", "duplicate", "nil_first", "foreign_id", "too_many", "score_count", "nonstring"])
def test_event_space_is_ordered_candidate_options_plus_one_nil(mutation):
    labels, scores = ["cand_" + "b" * 64, "__NIL__"], [1, 2]
    if mutation == "one_nil": labels, scores = ["__NIL__"], [1]
    elif mutation == "duplicate": labels, scores = [labels[0], labels[0], "__NIL__"], [1, 2, 3]
    elif mutation == "nil_first": labels.reverse()
    elif mutation == "foreign_id": labels[0] = "corpus-id-is-not-candidate-option"
    elif mutation == "too_many": labels, scores = [f"cand_{i:064x}" for i in range(21)] + ["__NIL__"], [0] * 22
    elif mutation == "score_count": scores.pop()
    else: labels[0] = False
    with pytest.raises(data.CalibrationDataError):
        event(labels=labels, raw_scores=scores)


def test_twenty_candidates_and_nil_are_the_inclusive_limit():
    labels = [f"cand_{i:064x}" for i in range(20)] + ["__NIL__"]
    result = event(labels=labels, raw_scores=list(range(21)), truth_kind="NIL", truth_label="__NIL__")
    assert len(result.labels) == data.MAX_LABELS == 21


@pytest.mark.parametrize("changes", [
    {"truth_kind": "UNJUDGED", "truth_label": None}, {"truth_kind": []},
    {"truth_kind": "NIL"}, {"truth_label": "__NIL__"}, {"truth_label": "cand_" + "0" * 64},
    {"split": "TRAIN"}, {"split": "DEV"}, {"split": "FROZEN_HOLDOUT"},
    {"schema_version": "old"}, {"post_id": False}, {"example_id": ""}, {"data_kind": []},
    {"base_model_sha256": None}, {"scorer_summary_sha256": "x" * 64},
])
def test_unknown_truth_partition_and_metadata_are_not_inferred(changes):
    with pytest.raises(data.CalibrationDataError):
        event(**changes)


@pytest.mark.parametrize("mutation", ["unknown_grade", "bad_artifact", "wrong_scope", "no_reviewer", "extra", "missing", "source_backed"])
def test_provenance_grade_and_artifact_are_explicit(mutation):
    provenance = dict(event().label_provenance)
    kwargs = {}
    if mutation == "unknown_grade": provenance["grade"] = "UNJUDGED"
    elif mutation == "bad_artifact": provenance["artifact_sha256"] = None
    elif mutation == "wrong_scope": provenance["scope"] = "MENTION_ROLE"
    elif mutation == "no_reviewer": provenance["reviewer"] = " "
    elif mutation == "extra": provenance["model_truth"] = True
    elif mutation == "missing": provenance.pop("artifact_sha256")
    else: kwargs["data_kind"] = "SOURCE_BACKED"
    with pytest.raises(data.CalibrationDataError):
        event(label_provenance=provenance, **kwargs)


def test_external_mutation_unknown_fields_and_explicit_sha_are_rejected():
    value = event().to_dict()
    value["raw_scores"][0] += 1
    with pytest.raises(data.CalibrationDataError, match="EVENT_SHA_MISMATCH"):
        data.CalibrationFitEvent.from_dict(value)
    value = event().to_dict()
    value["extra"] = None
    with pytest.raises(data.CalibrationDataError, match="EVENT_FIELDS_INVALID"):
        data.CalibrationFitEvent.from_dict(value)
    with pytest.raises(data.CalibrationDataError, match="EVENT_SHA_MUST_BE_COMPUTED"):
        event(event_sha256="0" * 64)


@pytest.mark.parametrize("field", ["training_split_manifest_sha256", "calibration_manifest_sha256",
    "scorer_fingerprint", "scorer_summary_sha256", "model_sha256", "base_model_sha256", "data_kind"])
def test_batch_requires_same_model_split_and_data_kind(field):
    kwargs = {field: "d" * 64, "example_id": "synthetic-example-2", "post_id": "synthetic-post-2"}
    if field == "data_kind":
        kwargs[field] = "SOURCE_BACKED"
        kwargs["label_provenance"] = {**dict(event().label_provenance), "grade": "MODEL_REFERENCE"}
    with pytest.raises(data.CalibrationDataError, match="MIXED_CAL_EVENT_BINDING"):
        data.validate_calibration_fit_events([event(), event(**kwargs)])


def test_batch_bounds_duplicates_and_expected_order_preserve_denominator():
    first, second = event(), event(example_id="synthetic-example-2", post_id="synthetic-post-2", truth_kind="NIL", truth_label="__NIL__")
    values = [first, second]
    assert data.validate_calibration_fit_events(values, expected_example_ids=[e.example_id for e in values]) == tuple(values)
    assert data.calibration_event_set_sha256(values) == data.canonical_sha256([e.to_dict() for e in values])
    assert data.calibration_event_set_sha256(values) != data.calibration_event_set_sha256(list(reversed(values)))
    for bad in ([], [first] * 257, [first, first], [first, event(example_id="another-id")], [first.to_dict()]):
        with pytest.raises(data.CalibrationDataError):
            data.validate_calibration_fit_events(bad)
    for ids in ([second.example_id, first.example_id], [first.example_id], [first.example_id, first.example_id]):
        with pytest.raises(data.CalibrationDataError, match="CAL_EVENT_UNIVERSE_MISMATCH"):
            data.validate_calibration_fit_events(values, expected_example_ids=ids)
