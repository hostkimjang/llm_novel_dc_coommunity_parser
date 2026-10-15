"""고정 NIL 모델 재생부터 평가 보고서 저장·재판독까지 검증한다. 자료는 합성이다."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools import run_candidate_reranker_evaluation as workflow


def _raw(value):
    return workflow.local._json_bytes(value)


def test_direct_cli_help_imports_from_its_own_repository():
    result = subprocess.run([sys.executable, str(Path(workflow.__file__).resolve()), '--help'],
        cwd=Path(workflow.__file__).resolve().parent.parent, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert '--bundle-sha256' in result.stdout and '--output-dir' in result.stdout


def test_semantic_evaluation_cli_replays_whole_frozen_and_saves_report(tmp_path, monkeypatch):
    from tests.candidate_reranker_semantic_calibration_fixtures import build_semantic_calibration_fixture
    from src.llm_batch.grounding import candidate_reranker_calibration as calibration
    fixture_path = tmp_path / 'fixture'
    fixture_path.mkdir()
    fixture = build_semantic_calibration_fixture(fixture_path)
    artifact = calibration.fit_temperature(fixture['calibration_events'],
        split_manifest=fixture['calibration_manifest'], policy=fixture['policy'])['artifact']
    project = tmp_path / 'inputs'
    bundle_path, pin, _ = write_bundle(project, fixture, artifact)
    monkeypatch.setattr(workflow, 'ROOT', project)
    result = workflow.evaluate_bundle(bundle_path=bundle_path, expected_sha256=pin, output_dir=tmp_path / 'evaluated')
    report = json.loads(Path(result['evaluation_report']['path']).read_bytes())
    assert report['counts']['expected_rows'] == report['counts']['calibration_bound_rows'] == 2
    assert report['quality_acceptance_claimed'] is False
    assert report['formal_kpi_status'] == 'NOT_ESTIMABLE'


def _ref(path, root):
    raw = path.read_bytes()
    return {'path': path.relative_to(root).as_posix(), 'sha256': workflow.local._sha(raw), 'bytes': len(raw)}


def write_bundle(root, fixture, artifact):
    """기존 합성 CAL fixture를 명시적인 평가 bundle 파일들로 저장한다."""
    root.mkdir()
    refs = {}
    for kind in ('source', 'evidence'):
        folder = root / kind; folder.mkdir(); mapped = {}
        for index, (key, raw) in enumerate(fixture[kind + '_payloads'].items()):
            path = folder / (str(index) + '.bin'); path.write_bytes(raw)
            mapped[key] = _ref(path, root)
        refs[kind] = mapped
    model_path = root / 'model.json'; model_path.write_bytes(Path(fixture['model_manifest_path']).read_bytes())
    artifact_path = root / 'artifact.json'; artifact_path.write_bytes(_raw(artifact.to_dict()))
    expected, observations, graphs = [], [], []
    for args in fixture['frozen_args']:
        example = deepcopy(args['example'])
        expected.append({**example, 'publication_scope_id': args['publication_scope_id']})
        row = next(r for r in fixture['training_manifest']['rows'] if r['assignment']['example_id'] == example['example_id'])
        receipt = deepcopy(args['raw_receipt'])
        receipt['binding'] = {**row['binding'], 'post_id': row['assignment']['post_id'],
            'publication_scope_id': args['publication_scope_id'], 'scope': 'ATTEMPT_LOCAL_OBSERVATION'}
        observations.append({'example_id': example['example_id'], 'receipt': receipt})
        graphs.append({'example': example, 'raw_receipt': deepcopy(args['raw_receipt']),
            'base_shadow': args['base_shadow'].to_dict(), 'generation_proof': args['generation_proof'].to_ledger_dict(),
            'retrieval_state': args['retrieval_state'].to_dict(), 'publication_scope_id': args['publication_scope_id'],
            'source_binding_sha256': args['source_binding_sha256']})
    value = {'schema_version': workflow.BUNDLE_SCHEMA, 'model_manifest': _ref(model_path, root),
        'calibration_artifact': _ref(artifact_path, root),
        'expected_scorer_summary_sha256': workflow.local._sha(_raw(fixture['scorer_summary'])),
        'training_manifest': fixture['training_manifest'],
        'expected_training_manifest_sha256': fixture['training_manifest']['manifest_sha256'],
        'calibration_manifest': fixture['calibration_manifest'].to_dict(),
        'expected_calibration_manifest_sha256': fixture['calibration_manifest'].manifest_sha256,
        'policy': fixture['policy'].to_dict(), 'source_files': refs['source'], 'evidence_files': refs['evidence'],
        'expected_rows': expected, 'observations': observations, 'frozen_rows': graphs}
    path = root / 'bundle.json'; path.write_bytes(_raw(value))
    return path, workflow.local._sha(path.read_bytes()), value


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    import socket
    from tests.candidate_reranker_calibration_fixtures import build_calibration_fixture
    from src.llm_batch.grounding import candidate_reranker_calibration as calibration
    from src.llm_batch.grounding import candidate_reranker_learned as learned
    from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('실제 연결 금지'))
    model_dir = tmp_path / 'fixture'; model_dir.mkdir()
    fixture = build_calibration_fixture(model_dir)
    artifact = calibration.fit_temperature(fixture['calibration_events'],
        split_manifest=fixture['calibration_manifest'], policy=fixture['policy'])['artifact']
    path, pin, value = write_bundle(tmp_path / 'inputs', fixture, artifact)
    for module, function in ((calibration, 'fit_temperature'), (learned, 'train_model'), (nil, 'train_model')):
        monkeypatch.setattr(module, function, lambda *a, **k: pytest.fail('평가 중 새 학습 금지'))
    return path, pin, value, fixture, artifact


def _replace(path, value):
    path.write_bytes(_raw(value))
    return workflow.local._sha(path.read_bytes())


def test_cli_replays_pinned_model_and_saves_exact_report_without_refit(bundle, tmp_path, capsys):
    path, pin, _, _, _ = bundle
    before = {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
    output = tmp_path / 'output'
    assert workflow.main(['--bundle', str(path), '--bundle-sha256', pin, '--output-dir', str(output)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['status'] == 'EVALUATED_AND_READBACK_VERIFIED'
    assert receipt['local_score_replay_count'] == receipt['expected_rows'] == 2
    assert receipt['model_training_executed'] is receipt['calibration_fit_executed'] is False
    assert receipt['actual_quality_evaluated'] is receipt['actual_performance_evaluated'] is False
    assert receipt['formal_kpi_status'] == 'NOT_ESTIMABLE'
    assert not (output / '.pending_report.json').exists()
    assert not (output / '.pending_receipt.json').exists()
    for name in ('evaluation_report', 'workflow_receipt'):
        ref = receipt[name]; raw = Path(ref['path']).read_bytes()
        assert len(raw) == ref['bytes'] and workflow.local._sha(raw) == ref['sha256']
    report = json.loads(Path(receipt['evaluation_report']['path']).read_bytes())
    workflow._validate_report(report)
    assert receipt['report_sha256'] == report['report_sha256']
    assert report['data_kind'] == 'SYNTHETIC_FIXTURE'
    saved = json.loads(Path(receipt['workflow_receipt']['path']).read_bytes())
    assert saved['receipt_sha256'] == workflow.local._sha(_raw({k: v for k, v in saved.items()
        if k not in saved['receipt_hash_excludes']}))
    assert {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()} == before
    for key in ('pid', 'priority_class', 'affinity_mask', 'logical_cpu_count', 'numeric_threads'):
        assert receipt['resources_start'][key] == receipt['resources_end'][key]


@pytest.mark.parametrize('fault', ['pin', 'source_sha', 'evidence_key', 'outside', 'absolute', 'unc', 'url',
    'extra', 'missing_observation', 'duplicate_expected', 'graph_order', 'artifact_model_same_file'])
def test_invalid_bundle_rejected_before_score_replay_or_output(bundle, tmp_path, monkeypatch, fault):
    path, pin, value, _, _ = bundle
    ref = next(iter(value['source_files'].values()))
    if fault == 'pin': pin = '0' * 64
    elif fault == 'source_sha': ref['sha256'] = '0' * 64
    elif fault == 'evidence_key':
        _, item = value['evidence_files'].popitem(); value['evidence_files']['0' * 64] = item
    elif fault == 'outside': ref['path'] = '../outside.bin'
    elif fault == 'absolute': ref['path'] = str(path.parent / ref['path'])
    elif fault == 'unc': ref['path'] = '//server/share/file'
    elif fault == 'url': ref['path'] = 'https://example.invalid/input'
    elif fault == 'extra': value['infer_missing_graph'] = True
    elif fault == 'missing_observation': value['observations'].pop()
    elif fault == 'duplicate_expected': value['expected_rows'][1]['example_id'] = value['expected_rows'][0]['example_id']
    elif fault == 'graph_order': value['frozen_rows'].reverse()
    else: value['calibration_artifact'] = deepcopy(value['model_manifest'])
    if fault != 'pin': pin = _replace(path, value)
    monkeypatch.setattr(workflow, '_replay_rows', lambda *a, **k: pytest.fail('잘못된 bundle의 score 재생 금지'))
    output = tmp_path / 'output'
    with pytest.raises((ValueError, OSError)):
        workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize('field', ['ranked_candidates', 'event_logits', 'nil_score', 'input_sha256', 'candidate_ranker_model_sha256'])
def test_resealed_score_must_match_pinned_local_model(bundle, tmp_path, field):
    path, _, value, _, _ = bundle
    receipt = value['observations'][0]['receipt']
    if field in ('ranked_candidates', 'event_logits'): receipt[field][0]['score'] += 0.125
    elif field == 'nil_score': receipt[field] += 0.125
    else: receipt[field] = '0' * 64
    receipt['receipt_sha256'] = workflow.local._sha(_raw({k: v for k, v in receipt.items()
        if k not in ('receipt_sha256', 'latency_ms', 'binding')}))
    pin = _replace(path, value)
    with pytest.raises(ValueError, match='재생 불일치'):
        workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_missing_graph_is_saved_as_incomplete_evaluation_not_invented(bundle, tmp_path):
    path, _, value, _, _ = bundle
    value['frozen_rows'] = []
    pin = _replace(path, value)
    receipt = workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=tmp_path / 'output')
    report = json.loads(Path(receipt['evaluation_report']['path']).read_bytes())
    assert report['counts']['expected_rows'] == report['counts']['observed_rows'] == 2
    assert report['quality_acceptance_claimed'] is False
    assert 'NOT_EVALUABLE' in _raw(report).decode()


@pytest.mark.parametrize('missing', [1, 2])
def test_real_runtime_unexecuted_receipts_keep_full_denominator(bundle, tmp_path, missing):
    from src.llm_batch.runtime.candidate_reranker import export_candidate_reranker_fields
    path, _, value, fixture, _ = bundle
    for row in value['observations'][:missing]:
        row['receipt'] = export_candidate_reranker_fields(None, fixture['scorer'],
            binding=row['receipt']['binding'])['candidate_reranker_shadow']
        assert row['receipt']['status'] == 'NOT_AVAILABLE'
        assert row['receipt']['reason_codes'] == ['PIPELINE_NOT_EXECUTED']
    value['frozen_rows'] = value['frozen_rows'][missing:]
    pin = _replace(path, value)
    receipt = workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=tmp_path / 'output')
    report = json.loads(Path(receipt['evaluation_report']['path']).read_bytes())
    assert receipt['local_score_replay_count'] == 2 - missing
    assert report['counts']['expected_rows'] == report['counts']['observed_rows'] == 2
    assert report['counts']['source_terminals']['NOT_AVAILABLE'] == missing
    assert report['quality_acceptance_claimed'] is False
    assert 'NOT_EVALUABLE' in _raw(report).decode()


def test_duplicate_json_and_nonfinite_numbers_fail_before_model_load(bundle, tmp_path, monkeypatch):
    path, _, _, _, _ = bundle
    from src.llm_batch.grounding import candidate_reranker_shadow as adapter
    monkeypatch.setattr(adapter, 'load_scorer', lambda *a, **k: pytest.fail('JSON 검사 전 모델 로드'))
    for invalid in (b'{"schema_version":1,"schema_version":2}', b'{"number":1e999}'):
        path.write_bytes(invalid)
        with pytest.raises(ValueError):
            workflow.evaluate_bundle(bundle_path=path, expected_sha256=workflow.local._sha(invalid), output_dir=tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_input_changed_during_evaluation_is_detected_before_output(bundle, tmp_path, monkeypatch):
    from src.llm_batch.measurement import candidate_reranker_nil_evaluation as evaluation
    path, pin, value, _, _ = bundle
    source = path.parent / next(iter(value['source_files'].values()))['path']
    actual = evaluation.evaluate_frozen_nil_scores
    def changing(**kwargs):
        result = actual(**kwargs)
        source.write_bytes(source.read_bytes() + b'changed')
        return result
    monkeypatch.setattr(evaluation, 'evaluate_frozen_nil_scores', changing)
    with pytest.raises(ValueError):
        workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_storage_corruption_leaves_no_success_receipt(bundle, tmp_path, monkeypatch):
    path, pin, _, _, _ = bundle
    actual = workflow.local._write
    def corrupt(target, value):
        ref = actual(target, value)
        if target.name == '.pending_report.json':
            target.write_bytes(target.read_bytes() + b'corrupted')
        return ref
    monkeypatch.setattr(workflow.local, '_write', corrupt)
    output = tmp_path / 'output'
    with pytest.raises(ValueError): workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert not (output / 'workflow_receipt.json').exists()
    assert not (output / 'evaluation_report.json').exists()


def test_final_receipt_failure_preserves_report_without_success_marker(bundle, tmp_path, monkeypatch):
    path, pin, _, _, _ = bundle
    actual = workflow.calibration_io._rename_noreplace
    def failed_final(source, destination):
        if destination.name == 'workflow_receipt.json':
            raise OSError('injected final publication failure')
        return actual(source, destination)
    monkeypatch.setattr(workflow.calibration_io, '_rename_noreplace', failed_final)
    output = tmp_path / 'output'
    with pytest.raises(OSError, match='final publication failure'):
        workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert not (output / 'workflow_receipt.json').exists()
    workflow._validate_report(json.loads((output / 'evaluation_report.json').read_bytes()))


def test_existing_output_is_never_overwritten(bundle, tmp_path):
    path, pin, _, _, _ = bundle
    output = tmp_path / 'output'; output.mkdir(); sentinel = output / 'keep.bin'; sentinel.write_bytes(b'keep')
    with pytest.raises(ValueError, match='새 경로'):
        workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert sentinel.read_bytes() == b'keep' and list(output.iterdir()) == [sentinel]


def test_hardlinked_input_is_rejected(bundle, tmp_path):
    path, pin, value, _, _ = bundle
    source = path.parent / next(iter(value['source_files'].values()))['path']
    os.link(source, path.parent / 'second-link.bin')
    with pytest.raises(ValueError, match='단일 일반 파일'):
        workflow.evaluate_bundle(bundle_path=path, expected_sha256=pin, output_dir=tmp_path / 'output')
    assert not (tmp_path / 'output').exists()
