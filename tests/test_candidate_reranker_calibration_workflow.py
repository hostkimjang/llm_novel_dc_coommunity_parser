"""명시적 CAL bundle의 로컬 score 재생·학습·배타 저장·typed 재판독."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools import run_candidate_reranker_calibration as workflow
from tests.candidate_reranker_calibration_fixtures import build_calibration_fixture


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('network forbidden'))
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: pytest.fail('network forbidden'))


def _raw(value):
    return workflow.local._json_bytes(value)


def _ref(path, root):
    raw = path.read_bytes()
    return {'path': path.relative_to(root).as_posix(), 'sha256': workflow.local._sha(raw), 'bytes': len(raw)}


def _serialize_row(row):
    result = deepcopy(row)
    for key, method in (('base_shadow', 'to_dict'), ('generation_proof', 'to_ledger_dict'), ('retrieval_state', 'to_dict')):
        if type(result[key]) is not dict:
            result[key] = getattr(result[key], method)()
    return result


def write_bundle(root, fixture):
    root.mkdir(parents=True, exist_ok=True)
    maps = {}
    for name in ('source', 'evidence'):
        folder = root / name; folder.mkdir(); refs = {}
        for i, (key, raw) in enumerate(fixture[name + '_payloads'].items()):
            path = folder / (str(i) + '.bin')
            with path.open('xb') as stream: stream.write(raw)
            refs[key] = _ref(path, root)
        maps[name] = refs
    model = root / 'model_manifest.json'
    with model.open('xb') as stream: stream.write(Path(fixture['model_manifest_path']).read_bytes())
    bundle = {'schema_version': workflow.BUNDLE_SCHEMA, 'model_manifest': _ref(model, root),
        'expected_scorer_summary_sha256': workflow.local._sha(_raw(fixture['scorer_summary'])),
        'training_manifest': fixture['training_manifest'],
        'expected_training_manifest_sha256': fixture['training_manifest']['manifest_sha256'],
        'calibration_manifest': fixture['calibration_manifest'].to_dict(),
        'expected_calibration_manifest_sha256': fixture['calibration_manifest'].manifest_sha256,
        'policy': fixture['policy'].to_dict(), 'solver_config': {},
        'source_files': maps['source'], 'evidence_files': maps['evidence'],
        'calibration_rows': [_serialize_row(row) for row in fixture['cal_rows']],
        'expected_example_ids': list(fixture['expected_calibration_example_ids'])}
    path = root / 'bundle.json'
    with path.open('xb') as stream: stream.write(_raw(bundle))
    return path, workflow.local._sha(path.read_bytes()), bundle


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    fixture_dir = tmp_path / 'fixture'
    fixture_dir.mkdir()
    fixture = build_calibration_fixture(fixture_dir)
    project = tmp_path / 'project'
    path, expected, value = write_bundle(project, fixture)
    monkeypatch.setattr(workflow, 'ROOT', project)
    return path, expected, value, fixture


def _replace(path, value):
    path.write_bytes(_raw(value))
    return workflow.local._sha(path.read_bytes())


def test_actual_local_cli_fits_and_readbacks_v2_without_frozen_quality_claim(bundle, tmp_path, capsys):
    from src.llm_batch.grounding.candidate_set_calibration_shadow import calibration_artifact_from_dict
    path, expected, _, fixture = bundle
    before = {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
    output = tmp_path / 'new-output'
    assert workflow.main(['--bundle', str(path), '--bundle-sha256', expected, '--output-dir', str(output)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['status'] == 'FITTED_AND_READBACK_VERIFIED' and receipt['data_kind'] == 'SYNTHETIC_FIXTURE'
    assert receipt['calibration_executed'] is receipt['local_score_replay_executed'] is True
    assert receipt['model_training_executed'] is receipt['frozen_holdout_evaluated'] is False
    assert receipt['actual_quality_evaluated'] is receipt['public_apply'] is False
    assert receipt['formal_kpi_status'] == 'NOT_ESTIMABLE'
    assert not (output / '.pending_receipt.json').exists()
    for name in ('calibration_artifact', 'fit_receipt', 'fit_report', 'workflow_receipt'):
        ref = receipt[name]; raw = Path(ref['path']).read_bytes()
        assert workflow.local._sha(raw) == ref['sha256'] and len(raw) == ref['bytes']
    artifact = calibration_artifact_from_dict(json.loads(Path(receipt['calibration_artifact']['path']).read_bytes()))
    artifact.validate_against(fixture['calibration_manifest'], fixture['policy'])
    assert artifact.schema_version == 'candidate_set_calibration_artifact_v2'
    assert artifact.temperature == receipt['temperature'] > 0
    assert json.loads(Path(receipt['fit_receipt']['path']).read_bytes()) == artifact.fit_receipt.to_dict()
    saved = json.loads(Path(receipt['workflow_receipt']['path']).read_bytes())
    assert saved['receipt_sha256'] == workflow.local._sha(_raw({k: v for k, v in saved.items()
        if k not in saved['receipt_hash_excludes']}))
    assert {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()} == before
    assert receipt['resources_start']['status'] == 'LOW_LOAD_VERIFIED'
    assert receipt['resources_end']['status'] == 'OBSERVED'
    for key in ('pid', 'priority_class', 'affinity_mask', 'logical_cpu_count', 'numeric_threads'):
        assert receipt['resources_start'][key] == receipt['resources_end'][key]


@pytest.mark.parametrize('fault', ['bundle_sha', 'source_sha', 'evidence_key', 'outside', 'absolute', 'unc',
    'url', 'extra_key', 'missing_id', 'duplicate_id', 'row_order', 'foreign_split', 'row_limit'])
def test_invalid_bundle_fails_before_solver_and_output(bundle, tmp_path, monkeypatch, fault):
    from src.llm_batch.grounding import candidate_reranker_calibration as core
    path, expected, value, _ = bundle; ref = next(iter(value['source_files'].values()))
    if fault == 'bundle_sha': expected = '0' * 64
    elif fault == 'source_sha': ref['sha256'] = '0' * 64
    elif fault == 'evidence_key':
        _, item = value['evidence_files'].popitem(); value['evidence_files']['0' * 64] = item
    elif fault == 'outside': ref['path'] = '../outside.bin'
    elif fault == 'absolute': ref['path'] = str(path.parent / ref['path'])
    elif fault == 'unc': ref['path'] = '//server/shared/source'
    elif fault == 'url': ref['path'] = 'https://example.invalid/source'
    elif fault == 'extra_key': value['auto_generate_graph'] = True
    elif fault == 'missing_id': value['expected_example_ids'].pop()
    elif fault == 'duplicate_id': value['expected_example_ids'][1] = value['expected_example_ids'][0]
    elif fault == 'row_order': value['calibration_rows'].reverse()
    elif fault == 'row_limit': value['expected_example_ids'] = ['limit-example-' + str(i) for i in range(257)]
    else: value['calibration_rows'][0]['example']['example_id'] = 'foreign-frozen-example'
    if fault != 'bundle_sha': expected = _replace(path, value)
    monkeypatch.setattr(core, 'fit_temperature', lambda *a, **k: pytest.fail('invalid input reached solver'))
    monkeypatch.setattr(workflow, '_replay_rows', lambda *a, **k: pytest.fail('invalid input reached score replay'))
    output = tmp_path / 'output'
    with pytest.raises((ValueError, OSError)):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize('field', ['ranked_candidates', 'event_logits', 'nil_score', 'input_sha256',
                                 'model_sha256', 'training_split_manifest_sha256'])
def test_resealed_supplier_scores_must_match_pinned_model_replay(bundle, tmp_path, monkeypatch, field):
    from src.llm_batch.grounding import candidate_reranker_calibration as core
    path, _, value, _ = bundle; receipt = value['calibration_rows'][0]['raw_receipt']
    if field == 'ranked_candidates': receipt[field][0]['score'] += 0.5
    elif field == 'event_logits': receipt[field][0]['score'] += 0.5
    elif field == 'nil_score': receipt[field] += 0.5
    else: receipt[field] = '0' * 64
    receipt['receipt_sha256'] = workflow.local._sha(_raw({k: v for k, v in receipt.items()
        if k not in ('receipt_sha256', 'latency_ms', 'binding')}))
    expected = _replace(path, value)
    monkeypatch.setattr(core, 'fit_temperature', lambda *a, **k: pytest.fail('foreign score reached solver'))
    with pytest.raises(ValueError, match='재생 불일치'):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_existing_output_is_preserved(bundle, tmp_path):
    path, expected, _, _ = bundle
    output = tmp_path / 'output'; output.mkdir(); marker = output / 'keep.txt'; marker.write_bytes(b'preserve')
    with pytest.raises(ValueError, match='새 경로'):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert marker.read_bytes() == b'preserve'


def test_public_parser_readback_failure_has_no_success_receipt(bundle, tmp_path, monkeypatch):
    from src.llm_batch.grounding import candidate_set_calibration_shadow as legacy
    path, expected, _, _ = bundle
    def fail(*args, **kwargs): raise ValueError('readback rejected')
    monkeypatch.setattr(legacy, 'calibration_artifact_from_dict', fail)
    output = tmp_path / 'output'
    with pytest.raises(ValueError, match='readback rejected'):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert (output / 'calibration_artifact.json').is_file() and not (output / 'workflow_receipt.json').exists()


@pytest.mark.parametrize('field', ['binding', 'data_kind', 'solver', 'learning_evidence_sha256', 'policy_sha256'])
def test_resealed_fit_report_cannot_disagree_with_artifact_or_model(bundle, tmp_path, monkeypatch, field):
    from src.llm_batch.grounding import candidate_reranker_calibration as core
    path, expected, _, _ = bundle
    real_fit = core.fit_temperature
    def inconsistent_report(*args, **kwargs):
        fitted = real_fit(*args, **kwargs)
        report = fitted['fit_report']
        if field == 'binding': report[field]['model_sha256'] = '0' * 64
        elif field == 'data_kind': report[field] = 'SOURCE_BACKED'
        elif field == 'solver': report[field]['temperature'] += 0.25
        else: report[field] = '0' * 64
        report['report_sha256'] = workflow.local._sha(_raw({k: v for k, v in report.items() if k != 'report_sha256'}))
        return fitted
    monkeypatch.setattr(core, 'fit_temperature', inconsistent_report)
    with pytest.raises(ValueError, match='fit report'):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_source_mutation_during_fit_has_no_output(bundle, tmp_path, monkeypatch):
    from src.llm_batch.grounding import candidate_reranker_calibration as core
    path, expected, value, _ = bundle
    source = path.parent / next(iter(value['source_files'].values()))['path']
    original = source.read_bytes()
    real_fit = core.fit_temperature
    def change_input(*args, **kwargs):
        fitted = real_fit(*args, **kwargs)
        source.write_bytes(original + b'changed')
        return fitted
    monkeypatch.setattr(core, 'fit_temperature', change_input)
    with pytest.raises(ValueError, match='입력 파일 변경'):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_saved_raw_sha_is_checked_even_when_json_meaning_is_unchanged(bundle, tmp_path, monkeypatch):
    path, expected, _, _ = bundle
    real_write = workflow.local._write
    def changed_raw(file, payload):
        ref = real_write(file, payload)
        if file.name == 'calibration_artifact.json': file.write_bytes(file.read_bytes() + b' ')
        return ref
    monkeypatch.setattr(workflow.local, '_write', changed_raw)
    output = tmp_path / 'output'
    with pytest.raises(ValueError):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert (output / 'calibration_artifact.json').exists() and not (output / 'workflow_receipt.json').exists()


def test_runtime_wrapped_receipt_keeps_metadata_and_replays_only_model_fields(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from src.llm_batch.runtime.candidate_reranker import export_candidate_reranker_fields
    from tests.candidate_reranker_calibration_fixtures import bind_graph
    fixture_dir = tmp_path / 'fixture'; fixture_dir.mkdir()
    fixture = build_calibration_fixture(fixture_dir)
    for row in fixture['cal_rows']:
        assignment = next(r for r in fixture['training_manifest']['rows']
            if r['assignment']['example_id'] == row['example']['example_id'])
        original = deepcopy(row['raw_receipt'])
        binding = {**assignment['binding'], 'post_id': assignment['assignment']['post_id'],
                   'publication_scope_id': row['publication_scope_id']}
        row['raw_receipt'] = export_candidate_reranker_fields(
            SimpleNamespace(_candidate_reranker_shadow=original), fixture['scorer'],
            binding=binding)['candidate_reranker_shadow']
        assert row['raw_receipt']['status'] == 'SCORED_LEARNED'
        assert row['raw_receipt']['receipt_sha256'] != original['receipt_sha256']
        assert row['raw_receipt']['preselection_role_producer']['status'] == 'NOT_EXECUTED'
        args = {**fixture['common_kwargs'], **row}
        bind_graph(args)
        row['source_binding_sha256'] = args['source_binding_sha256']
    project = tmp_path / 'project'
    path, expected, _ = write_bundle(project, fixture)
    monkeypatch.setattr(workflow, 'ROOT', project)
    receipt = workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'output')
    assert receipt['status'] == 'FITTED_AND_READBACK_VERIFIED'
    saved = json.loads(Path(receipt['fit_receipt']['path']).read_bytes())
    assert [e['raw_receipt_sha256'] for e in saved['learning_evidence']['events']] == [
        row['raw_receipt']['receipt_sha256'] for row in fixture['cal_rows']]


@pytest.mark.parametrize('failure', ['partial_write', 'read_error', 'read_mismatch'])
def test_final_receipt_write_or_readback_failure_keeps_only_pending(bundle, tmp_path, monkeypatch, failure):
    path, expected, _, _ = bundle
    if failure == 'partial_write':
        real_write = workflow.local._write
        def incomplete(file, payload):
            if file.name == '.pending_receipt.json':
                with file.open('xb') as stream: stream.write(b'{"status":')
                raise OSError('injected final receipt write failure')
            return real_write(file, payload)
        monkeypatch.setattr(workflow.local, '_write', incomplete)
    else:
        real_read = workflow.local._read
        def failed_read(file, limit):
            if file.name == '.pending_receipt.json':
                if failure == 'read_error': raise OSError('injected final receipt read failure')
                return real_read(file, limit) + b'changed'
            return real_read(file, limit)
        monkeypatch.setattr(workflow.local, '_read', failed_read)
    output = tmp_path / 'output'
    with pytest.raises((OSError, ValueError)):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert (output / '.pending_receipt.json').exists()
    assert not (output / 'workflow_receipt.json').exists()


def test_final_receipt_publication_does_not_clobber_concurrent_destination(bundle, tmp_path, monkeypatch):
    path, expected, _, _ = bundle
    real_write = workflow.local._write
    marker = b'preexisting concurrent receipt'
    def concurrent_final(file, payload):
        ref = real_write(file, payload)
        if file.name == '.pending_receipt.json':
            with (file.parent / 'workflow_receipt.json').open('xb') as stream: stream.write(marker)
        return ref
    monkeypatch.setattr(workflow.local, '_write', concurrent_final)
    output = tmp_path / 'output'
    with pytest.raises(FileExistsError):
        workflow.calibrate_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert (output / 'workflow_receipt.json').read_bytes() == marker
    assert (output / '.pending_receipt.json').is_file()
