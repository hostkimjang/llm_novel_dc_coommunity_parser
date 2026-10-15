"""새 의미 특징의 CAL/FROZEN 실제 로컬 연결과 실패 분모. root 묶음 실행 전용."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from src.llm_batch.grounding import candidate_reranker_calibration as fit
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.grounding import candidate_set_calibration_shadow as legacy
from src.llm_batch.measurement import candidate_reranker_nil_evaluation as evaluation
from src.llm_batch.runtime.candidate_reranker import export_candidate_reranker_fields
from tools import run_candidate_reranker_calibration as workflow
from tests.candidate_reranker_semantic_calibration_fixtures import build_semantic_calibration_fixture
from tests.candidate_reranker_calibration_fixtures import build_calibration_fixture, raw, sha
from tests.test_candidate_reranker_calibration_workflow import write_bundle
from tests.test_candidate_reranker_nil_evaluation import inputs, snapshot, reseal


@pytest.mark.parametrize("backend", ["PAIRWISE_LINEAR_V1", "NIL_AUGMENTED_LINEAR_V1"])
def test_bridge_uses_producer_composite_feature_fingerprint(backend):
    from src.llm_batch.grounding import candidate_reranker_learned as pairwise
    from src.llm_batch.grounding import candidate_reranker_nil_learned as nil

    module = nil if backend == nil.BACKEND else pairwise
    # summary 지문 생성만 검산하는 최소 메타데이터. 모델 적격성은 아래 실제 학습 fixture가 검산한다.
    model_metadata = {
        "schema_version": "summary_projection_fixture_v2", "backend": backend,
        "feature_schema": module.FEATURE_SCHEMA_V2,
        "feature_contract": module._contract(module.FEATURE_SCHEMA_V2),
        "data_kind": "SYNTHETIC_FIXTURE",
        "training_binding": {"split_manifest_sha256": "1" * 64},
        "base_model": {"fixture": "SUMMARY_PROJECTION_ONLY"},
    }
    summary = adapter._summary("2" * 64, available=True, learned_model=model_metadata)
    assert bridge.semantic_model_fields(summary) == bridge.SEMANTIC_MODEL_FIELDS
    invalid_fingerprints = (
        bridge.canonical_sha256(model_metadata["feature_contract"]),
        bridge.canonical_sha256({"frozen_view_contract": {},
                                 "learned_feature_contract": model_metadata["feature_contract"]}),
    )
    for invalid in invalid_fingerprints:
        changed = {**summary, "feature_schema_sha256": invalid}
        with pytest.raises(bridge.EventBridgeError, match="SEMANTIC_MODEL_CONTRACT_MISMATCH"):
            bridge.semantic_model_fields(changed)


@pytest.fixture(scope="module")
def fixture(tmp_path_factory):
    return build_semantic_calibration_fixture(tmp_path_factory.mktemp("semantic-calibration"))


@pytest.fixture(scope="module")
def artifact(fixture):
    return fit.fit_temperature(fixture["calibration_events"],
        split_manifest=fixture["calibration_manifest"], policy=fixture["policy"])["artifact"]


def test_semantic_whole_cal_and_frozen_bind_actual_producer_and_preserve_inputs(fixture, artifact):
    args = inputs(fixture, artifact)
    before = snapshot(args)
    for row in fixture["cal_rows"]:
        receipt = row["raw_receipt"]
        source = fixture["semantic_inputs"][row["example"]["example_id"]]
        assert receipt["semantic_consumption"]["status"] == "SCORED"
        assert receipt["semantic_input_sha256"] == source["input_sha256"]
        assert source["observation"]["score_consumption_status"] == "NOT_CONSUMED_MODEL_POLICY_UNBOUND"
        assert set(("primary", "previous", "comparison")) <= {k for k, v in source["observation"]["counts"].items() if v}
    assert len(fixture["calibration_events"]) == len(fixture["frozen_vectors"]) == 2
    assert all(v.feature_schema_version == bridge.FEATURE_SCHEMA_V2 for v in fixture["frozen_vectors"].values())
    # 평가 API는 고정 raw score와 CAL 근거만 소비한다. scorer/학습기/새 fit 호출 금지.
    with patch.object(adapter.FrozenCandidateRerankerShadow, "score", side_effect=AssertionError("평가기 재점수화 금지")), \
         patch.object(fit, "fit_temperature", side_effect=AssertionError("평가기 신규 fit 금지")):
        report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["counts"]["expected_rows"] == report["counts"]["calibration_bound_rows"] == 2
    assert report["rank_metrics"]["score_coverage"]["value"] == 1
    assert report["quality_acceptance_claimed"] is report["actual_quality_evaluated"] is False
    assert report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert snapshot(args) == before


def test_cal_cli_replays_semantic_input_saves_and_reads_new_artifact(fixture, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    bundle, pinned, _ = write_bundle(project, fixture)
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    monkeypatch.setattr(workflow, "ROOT", project)
    result = workflow.calibrate_bundle(bundle_path=bundle, expected_sha256=pinned, output_dir=tmp_path / "new-fit")
    saved = legacy.calibration_artifact_from_dict(json.loads(Path(result["calibration_artifact"]["path"]).read_bytes()))
    assert result["status"] == "FITTED_AND_READBACK_VERIFIED"
    assert saved.fit_receipt.to_dict()["learning_evidence"]["binding"]["model_sha256"] == fixture["scorer_summary"]["model_sha256"]
    for args in fixture["frozen_args"]:
        vector = bridge.build_frozen_event_score(**args)
        assignment = next(row for row in fixture["calibration_manifest"].assignments
                          if row.example_id == vector.example_id)
        shadow = legacy.build_calibration_shadow(args["base_shadow"], score_vector=vector,
            artifact=saved, split_manifest=fixture["calibration_manifest"], policy=fixture["policy"],
            assignment=assignment)
        assert shadow.probability_status == legacy.CALIBRATED_BOUND_STATUS
        assert sum(p.probability_mass for p in shadow.event_probabilities) == legacy.PROBABILITY_SCALE
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("field", ["semantic_input_sha256", "semantic_observation_sha256"])
def test_resealed_consumption_must_match_captured_artifact(fixture, artifact, field):
    args = inputs(fixture, artifact)
    receipt = args["observations"][0]["receipt"]
    receipt["semantic_consumption"][field] = "a" * 64
    if field == "semantic_input_sha256":
        receipt[field] = "a" * 64
    reseal(receipt)
    args["frozen_rows"] = []
    with pytest.raises(ValueError, match="SEMANTIC_CONSUMPTION_ARTIFACT_MISMATCH"):
        evaluation.evaluate_frozen_nil_scores(**args)


@pytest.mark.parametrize("fault", ["missing_artifact", "raw_sha", "old_capture", "source_binding_v1", "policy"])
def test_semantic_bridge_rejects_missing_or_cross_version_evidence(fixture, fault):
    args = deepcopy(fixture["frozen_args"][0])
    capture = json.loads(args["evidence_payloads"][args["example"]["capture_sha256"]])
    if fault == "missing_artifact":
        args["evidence_payloads"].pop(capture["semantic_input_sha256"])
    elif fault == "raw_sha":
        args["evidence_payloads"][capture["semantic_input_sha256"]] += b" "
    elif fault == "old_capture":
        capture["schema_version"] = "reranker_preselection_capture_v1"
        capture.pop("semantic_input_sha256")
        encoded = raw(capture)
        args["evidence_payloads"][sha(encoded)] = encoded
        args["example"]["capture_sha256"] = sha(encoded)
    elif fault == "source_binding_v1":
        value = json.loads(args["evidence_payloads"][args["source_binding_sha256"]])
        value["schema_version"] = "candidate_reranker_event_source_binding_v1"
        value.pop("semantic_input_sha256")
        encoded = raw(value)
        args["source_binding_sha256"] = sha(encoded)
        args["evidence_payloads"][sha(encoded)] = encoded
    else:
        args["scorer_summary"]["semantic_policy_sha256"] = "a" * 64
        args["expected_scorer_summary_sha256"] = bridge.canonical_sha256(args["scorer_summary"])
    with pytest.raises(ValueError):
        bridge.build_frozen_event_score(**args)


@pytest.mark.parametrize("terminal", ["UNAVAILABLE_MODEL", "NOT_EXECUTED", "INVALID_INPUT"])
def test_real_failure_receipts_preserve_whole_semantic_frozen_denominator(fixture, artifact, terminal):
    args = inputs(fixture, artifact)
    prior = args["observations"][0]["receipt"]
    if terminal == "UNAVAILABLE_MODEL":
        scorer = adapter.unavailable_scorer("MODEL_UNAVAILABLE", expected_sha256=fixture["scorer_summary"]["model_manifest_sha256"])
        receipt = scorer.score(args["expected_rows"][0]["frozen_view"])
    elif terminal == "NOT_EXECUTED":
        receipt = export_candidate_reranker_fields(None, fixture["scorer"], binding=prior["binding"])["candidate_reranker_shadow"]
    else:
        # v2 모델에 의미 입력을 주지 않은 실제 adapter terminal.
        receipt = fixture["scorer"].score(args["expected_rows"][0]["frozen_view"])
    receipt["binding"] = prior["binding"]
    args["observations"][0]["receipt"] = receipt
    args["frozen_rows"] = args["frozen_rows"][1:]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["counts"]["expected_rows"] == 2
    assert report["rank_metrics"]["score_coverage"]["value"] == .5
    assert report["rows"][0]["action"] == "UNAVAILABLE"
    assert report["calibration_evaluation"]["status"] == "NOT_EVALUABLE"


def test_new_model_rejects_old_cal_artifact_and_missing_frozen_row(fixture, artifact, tmp_path):
    old = build_calibration_fixture(tmp_path)
    old_artifact = fit.fit_temperature(old["calibration_events"], split_manifest=old["calibration_manifest"], policy=old["policy"])["artifact"]
    with pytest.raises(ValueError):
        evaluation.evaluate_frozen_nil_scores(**inputs(fixture, old_artifact))
    args = inputs(fixture, artifact)
    args["expected_rows"].pop()
    args["observations"].pop()
    args["frozen_rows"].pop()
    with pytest.raises(ValueError, match="FULL_FROZEN_UNIVERSE_ORDER_REQUIRED"):
        evaluation.evaluate_frozen_nil_scores(**args)


def test_cli_replay_rejects_resealed_semantic_receipt_before_fit(fixture):
    rows = deepcopy(fixture["cal_rows"])
    rows[0]["raw_receipt"]["semantic_input_sha256"] = "b" * 64
    rows[0]["raw_receipt"]["semantic_consumption"]["semantic_input_sha256"] = "b" * 64
    reseal(rows[0]["raw_receipt"])
    with pytest.raises(ValueError, match="재생 불일치"):
        workflow._replay_rows(fixture["scorer"], rows, training_manifest=fixture["training_manifest"],
            source_payloads=fixture["source_payloads"], evidence_payloads=fixture["evidence_payloads"])


def test_real_alias_frozen_capture_after_whole_cal_fit_and_evaluation(tmp_path, monkeypatch):
    from src.llm_batch.grounding.candidate_reranker_capture import build_capture, validate_capture
    from src.llm_batch.grounding.candidate_reranker_learned import _features, FEATURE_NAMES
    from src.llm_batch.grounding.candidate_reranker_semantic_input import semantic_exposure_requirements
    from src.llm_batch.grounding.reranker_training_split import validate_training_split
    fixture_dir = tmp_path / "alias-fixture"
    fixture_dir.mkdir()
    bundle = build_semantic_calibration_fixture(fixture_dir, with_alias=True)
    alias_ids = [eid for eid, value in bundle["semantic_inputs"].items() if value["alias_evidence"] is not None]
    assert len(alias_ids) == 1
    eid = alias_ids[0]
    row = next(r for r in bundle["training_manifest"]["rows"] if r["assignment"]["example_id"] == eid)
    assert row["assignment"]["split"] == "FROZEN_HOLDOUT"
    assert validate_training_split(bundle["training_manifest"], source_payloads=bundle["source_payloads"],
        evidence_payloads=bundle["evidence_payloads"])["status"] == "VALID"
    value = bundle["semantic_inputs"][eid]
    requirement = semantic_exposure_requirements(value)[0]
    assert requirement["source_id"] in row["source_ids"] and requirement["review_source_id"] in row["source_ids"]
    for other in bundle["training_manifest"]["rows"]:
        if other["assignment"]["split"] != "FROZEN_HOLDOUT":
            assert all(requirement["alias_family_id"] not in e["alias_family_ids"] for e in other["exposures"])
    assert any(vector[FEATURE_NAMES.index("alias_substring")] == 1 for vector in _features(value["enriched_view"]))
    # 별칭이 없는 전체 CAL로 고정한 동일 v2 모델의 온도를 저장·재판독한다.
    assert all(bundle["semantic_inputs"][r["example"]["example_id"]]["alias_evidence"] is None for r in bundle["cal_rows"])
    project = tmp_path / "project"
    path, pinned, _ = write_bundle(project, bundle)
    before = {p: p.read_bytes() for folder in (project, fixture_dir) for p in folder.rglob("*") if p.is_file()}
    monkeypatch.setattr(workflow, "ROOT", project)
    receipt = workflow.calibrate_bundle(bundle_path=path, expected_sha256=pinned, output_dir=tmp_path / "alias-cal")
    stored = legacy.calibration_artifact_from_dict(json.loads(Path(receipt["calibration_artifact"]["path"]).read_bytes()))
    frozen = next(args for args in bundle["frozen_args"] if args["example"]["example_id"] == eid)
    captured = build_capture(frozen["example"]["frozen_view"], frozen["raw_receipt"], value["retrieval_receipt"],
        bundle["scorer_summary"], semantic_input=value, evidence_payloads=bundle["evidence_payloads"])
    assert validate_capture(captured) == captured and captured["schema_version"] == "candidate_reranker_capture_v2"
    assert captured["semantic_input"]["input_sha256"] == frozen["raw_receipt"]["semantic_input_sha256"]
    assert requirement["review_payload_sha256"] in captured["semantic_payloads_base64"]
    vector = bridge.build_frozen_event_score(**frozen)
    assignment = next(r for r in bundle["calibration_manifest"].assignments if r.example_id == eid)
    shadow = legacy.build_calibration_shadow(frozen["base_shadow"], vector, stored, bundle["policy"],
        split_manifest=bundle["calibration_manifest"], assignment=assignment)
    assert shadow.probability_status == legacy.CALIBRATED_BOUND_STATUS
    assert sum(p.probability_mass for p in shadow.event_probabilities) == legacy.PROBABILITY_SCALE
    report = evaluation.evaluate_frozen_nil_scores(**inputs(bundle, stored))
    assert report["counts"]["calibration_bound_rows"] == report["counts"]["expected_rows"] == 2
    assert report["counts"]["observed_rows"] == 2 and report["rank_metrics"]["score_coverage"]["value"] == 1
    assert report["actual_quality_evaluated"] is report["quality_acceptance_claimed"] is False
    assert {p: p.read_bytes() for p in before} == before
