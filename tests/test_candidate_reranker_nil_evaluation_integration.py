"""실제 합성 TRAIN/CAL 산출물을 독립 수치·구형 판독과 대조한다.

fixture 준비에서만 학습/새 파일을 만들며 평가 구간은 순수 판독이어야 한다.
합성 성공을 실제 자료의 품질 수용이나 공개 결과 변경으로 해석하지 않는다.
"""
from copy import deepcopy
import builtins
import hashlib
import io
import json
import math
import os
from pathlib import Path
import socket

import pytest

from tests.candidate_reranker_calibration_fixtures import build_calibration_fixture
from src.llm_batch.grounding import candidate_reranker_calibration as temperature
from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from src.llm_batch.grounding import candidate_reranker_learned as pairwise
from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.grounding import candidate_set_calibration_shadow as legacy
from src.llm_batch.grounding import reranker_training_split as split
from src.llm_batch.measurement import candidate_reranker_evaluation as raw_evaluation
from src.llm_batch.measurement import candidate_reranker_nil_evaluation as evaluation


def _raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_raw(value)).hexdigest()


def _rows(bundle, args_list, scorer=None):
    expected, observations, graphs = [], [], []
    for args in args_list:
        example = deepcopy(args["example"])
        expected.append({**example, "publication_scope_id": args["publication_scope_id"]})
        row = next(r for r in bundle["training_manifest"]["rows"]
                   if r["assignment"]["example_id"] == example["example_id"])
        receipt = deepcopy(args["raw_receipt"]) if scorer is None else scorer.score(example["frozen_view"])
        receipt["binding"] = {**row["binding"], "post_id": row["assignment"]["post_id"],
            "publication_scope_id": args["publication_scope_id"], "scope": "ATTEMPT_LOCAL_OBSERVATION"}
        observations.append({"example_id": example["example_id"], "receipt": receipt})
        graphs.append({"example": deepcopy(example), "raw_receipt": deepcopy(args["raw_receipt"]),
            "base_shadow": args["base_shadow"], "generation_proof": args["generation_proof"],
            "retrieval_state": args["retrieval_state"], "publication_scope_id": args["publication_scope_id"],
            "source_binding_sha256": args["source_binding_sha256"]})
    return expected, observations, graphs


@pytest.fixture(scope="module")
def fitted(tmp_path_factory):
    root = tmp_path_factory.mktemp("nil-evaluation-independent")
    bundle = build_calibration_fixture(root)
    result = temperature.fit_temperature(bundle["calibration_events"],
        split_manifest=bundle["calibration_manifest"], policy=bundle["policy"])
    path = root / "fitted-calibration.json"
    with path.open("xb") as stream:
        stream.write(_raw(result["artifact"].to_dict()))
    saved = path.read_bytes()
    artifact = legacy.calibration_artifact_from_dict(json.loads(saved))
    assert artifact.to_dict() == result["artifact"].to_dict()
    return bundle, result, artifact, path, saved


def _kwargs(fitted, *, policy=None, artifact=None):
    bundle, _, saved_artifact, _, _ = fitted
    expected, observations, graphs = _rows(bundle, bundle["frozen_args"])
    return {**bundle["common_kwargs"], "source_payloads": dict(bundle["source_payloads"]),
        "evidence_payloads": dict(bundle["evidence_payloads"]),
        "expected_rows": expected, "observations": observations, "frozen_rows": graphs,
        "policy": policy or bundle["policy"], "calibration_artifact": artifact or saved_artifact}


def _legacy_result(bundle, artifact, policy):
    shadows = {}
    for args in bundle["frozen_args"]:
        eid = args["example"]["example_id"]
        shadows[eid] = legacy.build_calibration_shadow(args["base_shadow"],
            bundle["frozen_vectors"][eid], artifact, policy,
            split_manifest=bundle["calibration_manifest"], assignment=bundle["frozen_assignments"][eid])
    return legacy.evaluate_frozen_holdout(split_manifest=bundle["calibration_manifest"],
        shadows=shadows, policy=policy, evidence_mode="SYNTHETIC_CONTRACT_ONLY",
        base_shadows=bundle["frozen_base_shadows"], score_vectors=bundle["frozen_vectors"],
        calibration_artifact=artifact), shadows


def _snapshot(kwargs):
    """제품 projection 없이 입력 전체의 관측 가능한 값을 고정한다."""
    def encode(value):
        if isinstance(value, bytes):
            return {"bytes_sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}
        if hasattr(value, "to_ledger_dict"):
            return encode(value.to_ledger_dict())
        if hasattr(value, "to_dict"):
            return encode(value.to_dict())
        if isinstance(value, dict):
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [encode(v) for v in value]
        return value
    return _raw(encode(kwargs))


def _assert_no_authority(report):
    for field in ("quality_acceptance_claimed", "actual_quality_evaluated", "publication_authority",
                  "public_apply", "central_db_write", "model_parameters_updated",
                  "new_calibration_fit_executed", "thresholds_reselected"):
        assert report[field] is False
    assert report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert all(row["action_applied"] is False for row in report["rows"])


def test_actual_synthetic_optimizer_saved_calibration_matches_legacy_and_independent_metrics(fitted):
    bundle, fit_report, artifact, _, _ = fitted
    assert bundle["model"]["training_binding"]["truth_counts"] == {"CANDIDATE": 1, "NIL": 1}
    assert fit_report["fit_report"]["optimizer_executed"] is True
    before_bases = {eid: base.to_dict() for eid, base in bundle["frozen_base_shadows"].items()}
    report = evaluation.evaluate_frozen_nil_scores(**_kwargs(fitted))
    expected, shadows = _legacy_result(bundle, artifact, bundle["policy"])
    assert report["calibration_evaluation"] == expected
    assert report["status"] == "DESCRIPTIVE_EVALUATION_COMPLETE"
    assert report["counts"]["expected_rows"] == report["counts"]["calibration_bound_rows"] == 2
    assert report["counts"]["truth_kinds"] == {"CANDIDATE": 1, "NIL": 1}
    for row in report["rows"]:
        shadow = shadows[row["example_id"]]
        assert row["calibration_shadow"] == shadow.to_dict()
        assert shadow.action_applied is False and shadow.operational_effect == "NONE_SHADOW_ONLY"
        assert sum(p.probability_mass for p in shadow.event_probabilities) == legacy.PROBABILITY_SCALE

    # corpus 순서는 legacy CandidateOption 순서와 반대다. 실제 ID bridge를 통해
    # gold의 후보 순위를 구하며 NIL logit은 후보 MRR의 순위 공간에 넣지 않는다.
    work = next(r for r in bundle["training_manifest"]["rows"]
                if r["assignment"]["split"] == "FROZEN_HOLDOUT" and r["assignment"]["truth_kind"] == "CANDIDATE")
    args = next(a for a in bundle["frozen_args"] if a["example"]["example_id"] == work["assignment"]["example_id"])
    mapping = {item["corpus_candidate_id"]: item["candidate_ids"][0] for item in work["r2_id_bridges"]}
    ordered = [mapping[r["candidate_id"]] for r in args["raw_receipt"]["ranked_candidates"]]
    truth = work["assignment"]["truth_label"]
    metric = report["rank_metrics"]["mrr_scored_work"]
    assert metric["denominator"] == 1 and metric["value"] == 1 / (ordered.index(truth) + 1)
    assert report["rank_metrics"]["gold_present_top1_accuracy"]["value"] == float(ordered[0] == truth)
    assert all("__NIL__" not in row["ranked_candidate_ids"] for row in report["rows"])

    # 교정 후 정수 probability mass가 실제 지표의 입력인지 수식으로 독립 대조한다.
    losses, briers = [], []
    for eid, shadow in shadows.items():
        truth = bundle["frozen_assignments"][eid].truth_label
        probs = {p.label: p.probability_mass / p.probability_scale for p in shadow.event_probabilities}
        losses.append(-math.log(probs[truth]))
        briers.append(sum((p - int(label == truth)) ** 2 for label, p in probs.items()))
    assert report["calibration_evaluation"]["metrics"]["log_loss"] == pytest.approx(sum(losses) / 2)
    assert report["calibration_evaluation"]["metrics"]["multiclass_brier"] == pytest.approx(sum(briers) / 2)
    assert {eid: base.to_dict() for eid, base in bundle["frozen_base_shadows"].items()} == before_bases
    _assert_no_authority(report)


def test_evaluation_is_deterministic_without_new_training_scoring_io_or_input_mutation(fitted, monkeypatch):
    kwargs = _kwargs(fitted)
    before, model_before = _snapshot(kwargs), _raw(fitted[0]["model"])
    def forbidden(*args, **kwargs):
        pytest.fail("평가 중 새 학습·모델 실행·I/O 금지")
    with monkeypatch.context() as guard:
        for module, name in ((nil, "train_model"), (nil, "train_nil_head"), (pairwise, "train_model"),
                             (temperature, "fit_temperature"), (adapter, "load_scorer"),
                             (adapter.FrozenCandidateRerankerShadow, "score"),
                             (builtins, "open"), (io, "open"), (os, "open"), (Path, "open"),
                             (socket.socket, "connect")):
            guard.setattr(module, name, forbidden)
        first = evaluation.evaluate_frozen_nil_scores(**kwargs)
        second = evaluation.evaluate_frozen_nil_scores(**kwargs)
    assert first == second
    assert before == _snapshot(kwargs) and model_before == _raw(fitted[0]["model"])
    assert fitted[3].read_bytes() == fitted[4]
    assert first["report_sha256"] == _sha({k: v for k, v in first.items() if k != "report_sha256"})
    _assert_no_authority(first)


def test_all_abstain_has_zero_conditional_denominators_without_removing_frozen_rows(fitted):
    bundle = fitted[0]
    policy = legacy.CalibrationEvaluationPolicy.create(**{
        **bundle["policy"].payload_without_policy_sha256(), "selector_max_error_probability": 0.0})
    artifact = temperature.fit_temperature(bundle["calibration_events"],
        split_manifest=bundle["calibration_manifest"], policy=policy)["artifact"]
    report = evaluation.evaluate_frozen_nil_scores(**_kwargs(fitted, policy=policy, artifact=artifact))
    expected, _ = _legacy_result(bundle, artifact, policy)
    assert report["calibration_evaluation"] == expected
    metrics = report["calibration_evaluation"]["metrics"]
    assert report["counts"]["expected_rows"] == report["counts"]["calibration_bound_rows"] == 2
    assert metrics["coverage"] == 0.0
    assert metrics["selective_risk"] is None
    assert metrics["top_label_accuracy_non_abstain"] is None
    assert metrics["nil_precision"] is None
    assert metrics["nil_recall"] == 0.0
    _assert_no_authority(report)


def test_missing_calibration_retains_raw_candidate_ranks_but_no_probability_metrics(fitted):
    kwargs = _kwargs(fitted)
    kwargs["calibration_artifact"] = None
    report = evaluation.evaluate_frozen_nil_scores(**kwargs)
    assert report["status"] == "NOT_EVALUABLE"
    assert report["counts"]["source_terminals"] == {"SCORED_LEARNED": 2}
    assert report["counts"]["expected_rows"] == report["counts"]["calibration_unavailable_rows"] == 2
    assert report["rank_metrics"]["score_coverage"]["value"] == 1.0
    assert all(v is None for v in report["calibration_evaluation"]["metrics"].values())
    assert all(row["calibration_shadow"] is None for row in report["rows"])
    _assert_no_authority(report)


def test_unjudged_reassignment_cannot_reuse_old_model_and_artifact_or_become_nil(fitted):
    kwargs = _kwargs(fitted)
    manifest = deepcopy(kwargs["training_manifest"])
    row = next(r for r in manifest["rows"]
               if r["assignment"]["split"] == "FROZEN_HOLDOUT" and r["assignment"]["truth_kind"] == "NIL")
    row["assignment"].update(truth_kind="UNJUDGED", truth_label=None)
    manifest = split.seal_manifest(manifest)
    assert split.validate_training_split(manifest, source_payloads=kwargs["source_payloads"],
        evidence_payloads=kwargs["evidence_payloads"])["status"] == "NOT_READY"
    old_cal = kwargs["calibration_manifest"]
    new_cal = legacy.CalibrationSplitManifest.create(
        assignments=[legacy.CalibrationSplitAssignment(**a) for a in split.calibration_assignments(manifest)],
        source_label_ledger_sha256=old_cal.source_label_ledger_sha256,
        assignment_seed_sha256=old_cal.assignment_seed_sha256)
    kwargs.update(training_manifest=manifest, expected_training_manifest_sha256=manifest["manifest_sha256"],
                  calibration_manifest=new_cal, expected_calibration_manifest_sha256=new_cal.manifest_sha256)
    with pytest.raises(ValueError, match="MODEL_TRAINING_SPLIT_MISMATCH"):
        evaluation.evaluate_frozen_nil_scores(**kwargs)
    assert row["assignment"]["truth_kind"] == "UNJUDGED" and row["assignment"]["truth_label"] is None


def test_existing_pairwise_v1_evaluator_still_uses_raw_thresholds_and_no_nil_policy(fitted, tmp_path):
    bundle = fitted[0]
    envelope = {"schema_version": adapter.LEARNED_MANIFEST_SCHEMA, "scorer_id": "independent-pairwise-v1",
        "backend": pairwise.BACKEND, "data_kind": "SYNTHETIC_FIXTURE", "feature_schema": pairwise.FEATURE_SCHEMA,
        "model": deepcopy(bundle["model"]["base_model"])}
    path = tmp_path / "pairwise.json"
    with path.open("xb") as stream:
        stream.write(_raw(envelope))
    scorer = adapter.load_scorer(path, expected_sha256=_sha(envelope))
    common = {"split_manifest": bundle["training_manifest"], "source_payloads": bundle["source_payloads"],
              "evidence_payloads": bundle["evidence_payloads"], "scorer_summary": scorer.summary()}
    expected, observations, _ = _rows(bundle, bundle["cal_rows"], scorer)
    fit = raw_evaluation.fit_calibration_thresholds(**common, expected_rows=expected, observations=observations,
        score_thresholds=[-100.0], margin_thresholds=[0.0], max_empirical_risk=1.0)
    assert fit["status"] == "CAL_POLICY_FROZEN"
    expected, observations, _ = _rows(bundle, bundle["frozen_args"], scorer)
    report = raw_evaluation.evaluate_frozen_scores(**common, expected_rows=expected, observations=observations,
        threshold_policy=fit["policy"], expected_policy_sha256=fit["policy"]["policy_sha256"])
    assert report["schema_version"] == "candidate_reranker_score_evaluation_v1"
    assert report["model_binding"]["backend"] == "PAIRWISE_LINEAR_V1"
    assert report["metrics"]["nil"]["predicted_nil"] == 0
    assert report["metrics"]["nil"]["precision"] is None
    assert report["probability_status"] == "NOT_AVAILABLE_UNCALIBRATED"
    assert report["quality_acceptance_claimed"] is False and report["publication_authority"] is False
