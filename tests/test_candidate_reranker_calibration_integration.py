"""실제 CAL optimizer 산출물의 저장·구형 FROZEN 소비와 v1 호환성을 검증한다."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from src.llm_batch.grounding import candidate_set_calibration_shadow as legacy
from src.llm_batch.grounding import candidate_reranker_calibration as learned
from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from tools.run_candidate_set_calibration_shadow_harness import _calibration_artifact_from_dict
from test_candidate_set_calibration_shadow_contract import _base_shadow, _policy, _split_manifest, _artifact


def test_legacy_artifact_readback_keeps_original_json_and_does_not_validate_learning():
    base = _base_shadow()
    manifest = _split_manifest(base.event_probabilities[0].label, base.candidate_set.candidate_set_fingerprint)
    policy = _policy()
    artifact = _artifact(manifest, policy)
    raw = artifact.to_dict()
    assert raw['schema_version'] == legacy.CALIBRATION_ARTIFACT_SCHEMA
    assert raw['fit_receipt']['schema_version'] == legacy.CALIBRATION_FIT_RECEIPT_SCHEMA
    assert 'learning_evidence' not in raw['fit_receipt']
    with patch.object(learned, 'validate_fit_evidence', side_effect=AssertionError('v1 has no learned evidence')):
        direct = legacy.calibration_artifact_from_dict(json.loads(json.dumps(raw)))
        harness = _calibration_artifact_from_dict(raw)
        direct.validate_against(manifest, policy)
    assert direct.to_dict() == harness.to_dict() == raw


@pytest.mark.parametrize('fault', ['extra', 'nonfinite', 'schema_list', 'v2_without_evidence', 'v1_with_evidence'])
def test_artifact_loader_rejects_malformed_or_mixed_schema(fault):
    base = _base_shadow()
    manifest = _split_manifest(base.event_probabilities[0].label, base.candidate_set.candidate_set_fingerprint)
    raw = _artifact(manifest, _policy()).to_dict()
    if fault == 'extra': raw['unexpected'] = 1
    if fault == 'nonfinite': raw['temperature'] = float('inf')
    if fault == 'schema_list': raw['schema_version'] = []
    if fault == 'v2_without_evidence':
        raw['schema_version'] = legacy.CALIBRATION_ARTIFACT_SCHEMA_V2
        raw['fit_receipt']['schema_version'] = legacy.CALIBRATION_FIT_RECEIPT_SCHEMA_V2
    if fault == 'v1_with_evidence': raw['fit_receipt']['learning_evidence'] = {}
    with pytest.raises(ValueError): legacy.calibration_artifact_from_dict(raw)


def _fit(tmp_path):
    from candidate_reranker_calibration_fixtures import build_calibration_fixture
    bundle = build_calibration_fixture(tmp_path)
    fitted = learned.fit_temperature(bundle['calibration_events'],
        split_manifest=bundle['calibration_manifest'], policy=bundle['policy'])
    return bundle, fitted


def test_saved_fitted_artifact_is_consumed_by_existing_frozen_shadow_without_public_changes(tmp_path):
    bundle, fitted = _fit(tmp_path)
    artifact = fitted['artifact']
    target = tmp_path / 'calibration_artifact.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(artifact.to_dict(), stream, ensure_ascii=False, allow_nan=False)
    reloaded = legacy.calibration_artifact_from_dict(json.loads(target.read_text(encoding='utf-8')))
    assert _calibration_artifact_from_dict(reloaded.to_dict()).to_dict() == artifact.to_dict()
    assert reloaded.schema_version == legacy.CALIBRATION_ARTIFACT_SCHEMA_V2
    assert reloaded.fit_receipt.schema_version == legacy.CALIBRATION_FIT_RECEIPT_SCHEMA_V2
    assert fitted['fit_report']['model_parameters_updated'] is False
    assert fitted['fit_report']['actual_performance_evaluated'] is False
    assert fitted['fit_report']['solver']['temperature'] == reloaded.temperature
    manifest, policy = bundle['calibration_manifest'], bundle['policy']
    before_model = deepcopy(bundle['model'])
    for args in bundle['frozen_args']:
        base = args['base_shadow']
        before = base.to_dict()
        vector = bridge.build_frozen_event_score(**args)
        assignment = next(row for row in manifest.assignments if row.example_id == vector.example_id)
        result = legacy.build_calibration_shadow(base, vector, reloaded, policy,
            split_manifest=manifest, assignment=assignment)
        assert result.probability_status == legacy.CALIBRATED_BOUND_STATUS
        assert sum(row.probability_mass for row in result.event_probabilities) == legacy.PROBABILITY_SCALE
        assert tuple(row.label for row in result.event_probabilities) == vector.labels
        assert result.calibration_artifact_sha256 == reloaded.artifact_sha256
        assert result.action_applied is False and result.operational_effect == 'NONE_SHADOW_ONLY'
        assert legacy.calibration_shadow_from_dict(result.to_dict()).to_dict() == result.to_dict()
        assert base.to_dict() == before
    assert bundle['model'] == before_model


@pytest.mark.parametrize('fault', ['temperature', 'policy', 'frozen', 'learning_result', 'evidence_missing'])
def test_resealed_v2_artifact_cannot_detach_the_actual_fit_evidence(tmp_path, fault):
    bundle, fitted = _fit(tmp_path)
    raw = fitted['artifact'].to_dict()
    receipt = raw['fit_receipt']
    if fault == 'temperature':
        raw['temperature'] = receipt['temperature'] = raw['temperature'] * 1.5
    if fault == 'policy': raw['policy_sha256'] = '0' * 64
    if fault == 'frozen': raw['frozen_holdout_fingerprint'] = '0' * 64
    if fault == 'learning_result':
        evidence = receipt['learning_evidence']
        evidence['solver']['temperature'] *= 1.5
        evidence['evidence_sha256'] = learned.canonical_sha256({k:v for k,v in evidence.items() if k != 'evidence_sha256'})
    if fault == 'evidence_missing': receipt.pop('learning_evidence')
    receipt['receipt_sha256'] = learned.canonical_sha256({k:v for k,v in receipt.items() if k != 'receipt_sha256'})
    raw['artifact_sha256'] = learned.canonical_sha256({k:v for k,v in raw.items() if k != 'artifact_sha256'})
    with pytest.raises(ValueError): legacy.calibration_artifact_from_dict(raw)
    if fault in ('policy', 'frozen'):
        invalid = legacy.CalibrationArtifact(**{k:v for k,v in raw.items() if k != 'fit_receipt'},
            fit_receipt=fitted['artifact'].fit_receipt)
        with pytest.raises(ValueError): invalid.validate_against(bundle['calibration_manifest'], bundle['policy'])
