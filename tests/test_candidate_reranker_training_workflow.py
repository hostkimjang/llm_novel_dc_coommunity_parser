"""로컬 bundle 파일 결속·배타 저장·실제 작은 optimizer/readback을 묶어 검증한다."""
import hashlib
import json
import math
import os
from pathlib import Path

import pytest

from tools import run_candidate_reranker_training as workflow
from tests.test_reranker_training_split import fixture as split_fixture


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def write_bundle(root: Path, *, manifest=None, source_payloads=None, evidence_payloads=None, examples=None,
                 parameters=None, backend=None, semantic_contract_sha256=None):
    root.mkdir(parents=True, exist_ok=True)
    if manifest is None:
        manifest, source_payloads, evidence_payloads = split_fixture()
    sources, evidence = {}, {}
    for prefix, payloads, refs in [('sources', source_payloads, sources), ('evidence', evidence_payloads, evidence)]:
        folder = root / prefix
        folder.mkdir()
        for index, (key, raw) in enumerate(payloads.items()):
            path = folder / (str(index) + '.bin')
            with path.open('xb') as stream:
                stream.write(raw)
            refs[key] = {'path': path.relative_to(root).as_posix(), 'sha256': sha(raw), 'bytes': len(raw)}
    bundle = {'schema_version': workflow.BUNDLE_SCHEMA if backend is None else workflow.BUNDLE_V2_SCHEMA,
        'scorer_id': 'synthetic-workflow-baseline',
        'parameters': parameters or {}, 'split_manifest': manifest, 'source_files': sources,
        'evidence_files': evidence, 'examples': examples or [], 'calibration_manifest': None,
        'expected_calibration_sha256': None}
    if backend is not None:
        bundle['backend'] = backend
    if semantic_contract_sha256 is not None:
        bundle.update(schema_version=workflow.BUNDLE_V3_SCHEMA,
                      semantic_feature_contract_sha256=semantic_contract_sha256)
    path = root / 'bundle.json'
    raw = raw_json(bundle)
    with path.open('xb') as stream:
        stream.write(raw)
    return path, sha(raw), bundle


def replace_bundle(path, bundle):
    raw = raw_json(bundle)
    path.write_bytes(raw)
    return sha(raw)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('network is forbidden'))
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: pytest.fail('network is forbidden'))


def test_bundle_exact_sources_and_evidence_are_read_without_generated_labels(tmp_path):
    path, expected, bundle = write_bundle(tmp_path / 'input')
    before = {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
    result = workflow.read_training_bundle(path, expected_sha256=expected)
    assert result['bundle'] == bundle
    assert result['source_payloads'] == split_fixture()[1]
    assert result['evidence_payloads'] == split_fixture()[2]
    assert {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()} == before
    assert sorted(result['snapshots']) == sorted(before)


@pytest.mark.parametrize('change', ['bundle_sha', 'source_sha', 'source_size', 'missing_source',
    'evidence_key', 'extra_key', 'schema', 'duplicate_json_key', 'nonfinite_json', 'float_overflow',
    'outside_ref', 'absolute_ref', 'url_ref', 'unc_ref', 'hardlink_ref'])
def test_invalid_bundle_fails_before_training_or_output(tmp_path, change):
    path, expected, bundle = write_bundle(tmp_path / 'input')
    ref = next(iter(bundle['source_files'].values()))
    if change == 'bundle_sha':
        expected = 'f' * 64
    elif change == 'source_sha':
        ref['sha256'] = 'a' * 64
    elif change == 'source_size':
        ref['bytes'] += 1
    elif change == 'missing_source':
        (path.parent / ref['path']).unlink()
    elif change == 'evidence_key':
        key, value = bundle['evidence_files'].popitem()
        bundle['evidence_files']['b' * 64] = value
    elif change == 'extra_key':
        bundle['run_remote'] = True
    elif change == 'schema':
        bundle['schema_version'] = 'unrecognized'
    elif change in ('duplicate_json_key', 'nonfinite_json', 'float_overflow'):
        raw = {'duplicate_json_key': b'{"schema_version":1,"schema_version":2}',
               'nonfinite_json': b'{"x":NaN}', 'float_overflow': b'{"x":1e999}'}[change]
        path.write_bytes(raw)
        expected = sha(raw)
    elif change == 'outside_ref':
        ref['path'] = '../outside.bin'
    elif change == 'absolute_ref':
        ref['path'] = str(path.parent / ref['path'])
    elif change == 'url_ref':
        ref['path'] = 'https://invalid.example/source'
    elif change == 'unc_ref':
        ref['path'] = '//server/share/source'
    else:
        os.link(path.parent / ref['path'], path.parent / 'source-hardlink.bin')
    if change not in ('bundle_sha', 'duplicate_json_key', 'nonfinite_json', 'float_overflow'):
        expected = replace_bundle(path, bundle)
    output = tmp_path / 'trained'
    with pytest.raises((ValueError, OSError)):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert not output.exists()


def test_existing_output_directory_is_rejected_even_when_empty(tmp_path):
    path, expected, _ = write_bundle(tmp_path / 'input')
    output = tmp_path / 'trained'
    output.mkdir()
    with pytest.raises(ValueError, match='새 경로'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert list(output.iterdir()) == []


@pytest.mark.parametrize('drive_type', [0, 1, 4])
def test_mapped_network_or_unknown_drive_rejected_before_file_read(tmp_path, monkeypatch, drive_type):
    path, expected, _ = write_bundle(tmp_path / 'input')
    monkeypatch.setattr(workflow, '_drive_type', lambda _: drive_type)
    monkeypatch.setattr(Path, 'open', lambda *a, **k: pytest.fail('nonlocal path must be rejected before open'))
    with pytest.raises(ValueError, match='비로컬 드라이브'):
        workflow.read_training_bundle(path, expected_sha256=expected)


def test_declared_local_drive_can_read_explicit_bundle(tmp_path, monkeypatch):
    path, expected, _ = write_bundle(tmp_path / 'input')
    monkeypatch.setattr(workflow, '_drive_type', lambda _: 3)
    assert workflow.read_training_bundle(path, expected_sha256=expected)['bundle_sha256'] == expected


@pytest.mark.parametrize('change', ['unknown_source_rights', 'unjudged', 'cross_split_work'])
def test_split_not_ready_or_invalid_never_creates_output(tmp_path, change):
    from src.llm_batch.grounding.reranker_training_split import seal_manifest
    path, expected, bundle = write_bundle(tmp_path / 'input')
    manifest = bundle['split_manifest']
    if change == 'unknown_source_rights':
        manifest['sources'][0]['rights_status'] = 'UNKNOWN'
    elif change == 'unjudged':
        manifest['rows'][0]['assignment']['truth_kind'] = 'UNJUDGED'
    else:
        manifest['rows'][1]['exposures'][1]['work_id'] = manifest['rows'][0]['exposures'][1]['work_id']
    bundle['split_manifest'] = seal_manifest(manifest)
    expected = replace_bundle(path, bundle)
    output = tmp_path / 'trained'
    with pytest.raises(ValueError, match='split'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert not output.exists()


def test_cli_requires_explicit_sha_and_reports_failure_without_output(tmp_path, capsys):
    path, _, _ = write_bundle(tmp_path / 'input')
    output = tmp_path / 'trained'
    with pytest.raises(SystemExit):
        workflow.main(['--bundle', str(path), '--output-dir', str(output)])
    assert workflow.main(['--bundle', str(path), '--bundle-sha256', 'e' * 64, '--output-dir', str(output)]) == 1
    assert '학습 실패' in capsys.readouterr().err
    assert not output.exists()


def learned_bundle(root):
    from tests.test_candidate_reranker_learned import training_fixture
    manifest, sources, evidence, examples = training_fixture()
    return write_bundle(root, manifest=manifest, source_payloads=sources, evidence_payloads=evidence,
                        examples=examples, parameters={'epochs': 8})


def test_real_optimizer_export_and_existing_scorer_readback_are_deterministic(tmp_path):
    from src.llm_batch.grounding.candidate_reranker_shadow import load_scorer
    path, expected, bundle = learned_bundle(tmp_path / 'input')
    before = {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
    first = workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained1')
    second = workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained2')
    assert first['status'] == second['status'] == 'TRAINED_AND_READBACK_VERIFIED'
    assert first['data_kind'] == 'SYNTHETIC_FIXTURE'
    assert first['model_manifest']['sha256'] == second['model_manifest']['sha256']
    assert first['formal_kpi_status'] == 'NOT_ESTIMABLE' and first['actual_performance_evaluated'] is False
    assert first['calibration_executed'] is first['frozen_holdout_evaluated'] is first['public_apply'] is False
    assert first['resources_start']['pid'] == first['resources_end']['pid'] == os.getpid()
    assert first['resources_start']['logical_cpu_count'] == first['resources_end']['logical_cpu_count'] == 1
    assert len(first['resources_end']['numeric_threads']) == 5
    assert all(value == '1' for value in first['resources_end']['numeric_threads'].values())
    if os.name == 'nt':
        assert first['resources_end']['priority_class'] == 16384 and first['resources_end']['affinity_mask'] == 2
    for name in ('model_manifest', 'training_report', 'workflow_receipt'):
        ref = first[name]
        raw = Path(ref['path']).read_bytes()
        assert len(raw) == ref['bytes'] and sha(raw) == ref['sha256']
    saved = json.loads(Path(first['workflow_receipt']['path']).read_bytes())
    body = {key: value for key, value in first.items() if key not in first['receipt_hash_excludes']}
    assert saved['receipt_sha256'] == first['receipt_sha256'] == sha(raw_json(body))
    scorer = load_scorer(first['model_manifest']['path'], expected_sha256=first['model_manifest']['sha256'])
    assert scorer.summary() == first['scorer_summary']
    scored = scorer.score(bundle['examples'][0]['frozen_view'])
    assert scored['status'] == 'SCORED_LEARNED' and scored['data_kind'] == 'SYNTHETIC_FIXTURE'
    assert {row['candidate_id'] for row in scored['ranked_candidates']} == {
        row['candidate_id'] for row in bundle['examples'][0]['frozen_view']['candidates']}
    assert scored['probability_status'] == 'NOT_AVAILABLE_UNCALIBRATED'
    assert scored['publication_authority'] is False
    assert {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()} == before
    with pytest.raises(ValueError, match='새 경로'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained1')


def test_actual_cli_trains_and_preserves_synthetic_scope(tmp_path, capsys):
    path, expected, _ = learned_bundle(tmp_path / 'input')
    assert workflow.main(['--bundle', str(path), '--bundle-sha256', expected,
                          '--output-dir', str(tmp_path / 'trained')]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['data_kind'] == 'SYNTHETIC_FIXTURE' and receipt['formal_kpi_status'] == 'NOT_ESTIMABLE'
    assert receipt['scorer_summary']['status'] == 'AVAILABLE_LEARNED'


def test_input_mutation_during_real_training_fails_before_export(tmp_path, monkeypatch):
    from src.llm_batch.grounding import candidate_reranker_learned as learned
    path, expected, bundle = learned_bundle(tmp_path / 'input')
    train = learned.train_model
    source = path.parent / next(iter(bundle['source_files'].values()))['path']
    def mutate(*args, **kwargs):
        result = train(*args, **kwargs)
        source.write_bytes(b'modified after optimizer')
        return result
    monkeypatch.setattr(learned, 'train_model', mutate)
    with pytest.raises(ValueError, match='입력 파일 변경'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')
    assert not (tmp_path / 'trained').exists()


def test_readback_failure_preserves_partial_outputs_without_success_receipt(tmp_path, monkeypatch):
    from src.llm_batch.grounding import candidate_reranker_shadow as shadow
    path, expected, _ = learned_bundle(tmp_path / 'input')
    def reject(*args, **kwargs):
        raise ValueError('readback mismatch')
    monkeypatch.setattr(shadow, 'load_scorer', reject)
    output = tmp_path / 'trained'
    with pytest.raises(ValueError, match='readback mismatch'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert (output / 'model_manifest.json').is_file() and (output / 'training_report.json').is_file()
    assert not (output / 'workflow_receipt.json').exists()


@pytest.mark.parametrize('field', ['model_sha256', 'training_binding', 'data_kind'])
def test_rebound_training_report_must_match_model_before_export(tmp_path, monkeypatch, field):
    from src.llm_batch.grounding import candidate_reranker_learned as learned
    path, expected, _ = learned_bundle(tmp_path / 'input')
    original = learned.train_model
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        result['training_report'][field] = 'foreign-report'
        return result
    monkeypatch.setattr(learned, 'train_model', changed)
    with pytest.raises(ValueError, match='모델과 보고서'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')
    assert not (tmp_path / 'trained').exists()


@pytest.mark.parametrize('backend', [None, workflow.PAIRWISE_BACKEND])
def test_v1_and_explicit_v2_pairwise_preserve_v2_manifest_without_nil_import(tmp_path, monkeypatch, backend):
    import builtins
    path, expected, bundle = learned_bundle(tmp_path / 'input')
    if backend is not None:
        bundle.update(schema_version=workflow.BUNDLE_V2_SCHEMA, backend=backend)
        expected = replace_bundle(path, bundle)
    original_import = builtins.__import__
    def reject_nil_import(name, globals=None, locals=None, fromlist=(), level=0):
        assert 'candidate_reranker_nil_learned' not in name
        assert 'candidate_reranker_nil_learned' not in (fromlist or ())
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, '__import__', reject_nil_import)
    receipt = workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')
    manifest = json.loads(Path(receipt['model_manifest']['path']).read_bytes())
    assert manifest['schema_version'] == 'candidate_reranker_manifest_v2'
    assert manifest['backend'] == receipt['backend'] == workflow.PAIRWISE_BACKEND
    assert receipt['scorer_summary']['training_status'] == 'TRAINED_PAIRWISE_LINEAR'
    assert receipt['scorer_summary'].get('nil_head_available') is not True


@pytest.mark.parametrize('change', ['v2_missing_backend', 'v1_with_nil_backend', 'unknown_backend',
                                   'module_path_backend', 'list_backend', 'null_backend', 'extra_v2_key'])
def test_backend_requires_explicit_v2_allowlisted_contract_before_training(tmp_path, monkeypatch, change):
    import builtins
    path, _, bundle = write_bundle(tmp_path / 'input', backend=workflow.NIL_BACKEND)
    if change == 'v2_missing_backend':
        bundle.pop('backend')
    elif change == 'v1_with_nil_backend':
        bundle['schema_version'] = workflow.BUNDLE_SCHEMA
    elif change == 'unknown_backend':
        bundle['backend'] = 'NIL_AUTODETECT'
    elif change == 'module_path_backend':
        bundle['backend'] = 'src.llm_batch.grounding.candidate_reranker_nil_learned'
    elif change == 'list_backend':
        bundle['backend'] = [workflow.NIL_BACKEND]
    elif change == 'null_backend':
        bundle['backend'] = None
    else:
        bundle['auto_label_missing'] = True
    expected = replace_bundle(path, bundle)
    original_import = builtins.__import__
    def reject_trainer_import(name, globals=None, locals=None, fromlist=(), level=0):
        for module in ('candidate_reranker_nil_learned', 'candidate_reranker_learned'):
            assert module not in name and module not in (fromlist or ())
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, '__import__', reject_trainer_import)
    output = tmp_path / 'trained'
    with pytest.raises(ValueError, match='bundle'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert not output.exists()


def nil_bundle(root):
    from tests.test_candidate_reranker_learned import training_fixture
    manifest, sources, evidence, examples = training_fixture(include_nil=True)
    return write_bundle(root, manifest=manifest, source_payloads=sources, evidence_payloads=evidence,
                        examples=examples, backend=workflow.NIL_BACKEND,
                        parameters={'base': {'epochs': 8}, 'nil_head': {'epochs': 8}})


def test_explicit_nil_cli_trains_v3_manifest_with_raw_scores_and_no_calibration(tmp_path, capsys):
    from src.llm_batch.grounding import candidate_reranker_nil_learned as learned
    from src.llm_batch.grounding.candidate_reranker_shadow import load_scorer
    path, expected, bundle = nil_bundle(tmp_path / 'input')
    before = {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
    assert workflow.main(['--bundle', str(path), '--bundle-sha256', expected,
                          '--output-dir', str(tmp_path / 'trained')]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['status'] == 'TRAINED_AND_READBACK_VERIFIED'
    assert receipt['backend'] == workflow.NIL_BACKEND and receipt['data_kind'] == 'SYNTHETIC_FIXTURE'
    for name in ('model_manifest', 'training_report', 'workflow_receipt'):
        ref = receipt[name]
        raw = Path(ref['path']).read_bytes()
        assert sha(raw) == ref['sha256'] and len(raw) == ref['bytes']
    saved = json.loads(Path(receipt['workflow_receipt']['path']).read_bytes())
    assert saved['receipt_sha256'] == sha(raw_json({key: value for key, value in saved.items()
                                                  if key not in saved['receipt_hash_excludes']}))
    manifest = json.loads(Path(receipt['model_manifest']['path']).read_bytes())
    model = learned.validate_model(manifest['model'])
    report = json.loads(Path(receipt['training_report']['path']).read_bytes())
    assert manifest['schema_version'] == 'candidate_reranker_manifest_v3'
    assert manifest['backend'] == model['backend'] == report['backend'] == workflow.NIL_BACKEND
    assert manifest['feature_schema'] == learned.FEATURE_SCHEMA
    assert report['model_sha256'] == sha(raw_json(model))
    assert report['training_binding'] == model['training_binding']
    assert model['config']['epochs'] == model['base_model']['config']['epochs'] == 8
    assert len(model['weights']) == len(learned.FEATURE_NAMES) and all(math.isfinite(v) for v in model['weights'])
    assert report['base_parameters_updated'] is False
    assert report['candidate_rows'] == report['nil_rows'] == 1
    scorer = load_scorer(receipt['model_manifest']['path'], expected_sha256=receipt['model_manifest']['sha256'])
    summary = scorer.summary()
    assert summary == receipt['scorer_summary']
    assert summary['nil_head_available'] is True
    assert summary['training_status'] == 'TRAINED_PAIRWISE_PLUS_NIL_HEAD'
    assert summary['model_kind'] == 'LEARNED_LINEAR_WITH_NIL_HEAD'
    assert summary['model_sha256'] == sha(raw_json(model))
    assert summary['training_split_manifest_sha256'] == bundle['split_manifest']['manifest_sha256']
    for example in bundle['examples']:
        scored = scorer.score(example['frozen_view'])
        assert scored['status'] == 'SCORED_LEARNED'
        assert type(scored['nil_score']) in (int, float) and math.isfinite(scored['nil_score'])
        assert scored['nil_probability'] is None
        assert [item['label'] for item in scored['event_logits']] == [
            row['candidate_id'] for row in example['frozen_view']['candidates']] + ['__NIL__']
        assert scored['probability_status'] == 'NOT_AVAILABLE_UNCALIBRATED'
        assert {row['candidate_id'] for row in scored['ranked_candidates']} == {
            row['candidate_id'] for row in example['frozen_view']['candidates']}
        assert scored['publication_authority'] is scored['public_apply'] is False
    for key in ('calibration_executed', 'frozen_holdout_evaluated', 'metric_evaluator_executed',
                'actual_performance_evaluated', 'publication_authority', 'public_apply', 'central_db_write'):
        assert receipt[key] is False
    assert receipt['formal_kpi_status'] == 'NOT_ESTIMABLE'
    assert {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('field', ['model_sha256', 'training_binding', 'data_kind', 'backend'])
def test_nil_training_report_binding_mismatch_fails_before_output(tmp_path, monkeypatch, field):
    from src.llm_batch.grounding import candidate_reranker_nil_learned as learned
    path, expected, _ = nil_bundle(tmp_path / 'input')
    original = learned.train_model
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        result['training_report'][field] = 'foreign-report'
        return result
    monkeypatch.setattr(learned, 'train_model', changed)
    with pytest.raises(ValueError, match='불일치'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')
    assert not (tmp_path / 'trained').exists()


def test_nil_unknown_core_parameters_are_not_silently_dropped(tmp_path):
    path, _, bundle = nil_bundle(tmp_path / 'input')
    bundle['parameters'] = {'unknown_optimizer': True}
    expected = replace_bundle(path, bundle)
    with pytest.raises(ValueError):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')
    assert not (tmp_path / 'trained').exists()


@pytest.mark.parametrize('field,bad', [('nil_head_available', False), ('training_status', 'TRAINED_PAIRWISE_LINEAR'),
                                     ('model_kind', 'LEARNED_LINEAR_BASELINE'),
                                     ('candidate_ranker_model_sha256', 'a' * 64),
                                     ('model_sha256', 'b' * 64), ('training_split_manifest_sha256', 'c' * 64)])
def test_nil_readback_without_bound_head_preserves_partial_output(tmp_path, monkeypatch, field, bad):
    from src.llm_batch.grounding import candidate_reranker_shadow as shadow
    path, expected, _ = nil_bundle(tmp_path / 'input')
    original = shadow.load_scorer
    def altered(*args, **kwargs):
        summary = original(*args, **kwargs).summary()
        summary[field] = bad
        class AlteredScorer:
            def summary(self):
                return summary
        return AlteredScorer()
    monkeypatch.setattr(shadow, 'load_scorer', altered)
    output = tmp_path / 'trained'
    with pytest.raises(ValueError, match='재판독 불일치'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert (output / 'model_manifest.json').is_file() and (output / 'training_report.json').is_file()
    assert not (output / 'workflow_receipt.json').exists()


def semantic_bundle(root, *, backend=workflow.NIL_BACKEND, with_alias=False):
    from tests.test_candidate_reranker_semantic_training import semantic_training_fixture
    from src.llm_batch.grounding.candidate_reranker_semantic_input import FEATURE_CONTRACT_SHA256
    manifest, sources, evidence, examples = semantic_training_fixture(root / 'fixture', with_alias=with_alias)
    parameters = {'base': {'epochs': 4}, 'nil_head': {'epochs': 4}} if backend == workflow.NIL_BACKEND else {'epochs': 4}
    return write_bundle(root / 'bundle', manifest=manifest, source_payloads=sources, evidence_payloads=evidence,
        examples=examples, backend=backend, parameters=parameters, semantic_contract_sha256=FEATURE_CONTRACT_SHA256)


@pytest.mark.parametrize('backend', [workflow.PAIRWISE_BACKEND, workflow.NIL_BACKEND])
def test_explicit_v3_bundle_trains_semantic_model_with_alias_and_readback(tmp_path, backend):
    from tests.test_candidate_reranker_semantic_training import _artifact
    from src.llm_batch.grounding.candidate_reranker_shadow import load_scorer
    path, expected, bundle = semantic_bundle(tmp_path / 'input', backend=backend, with_alias=True)
    before = {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
    receipt = workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')
    assert receipt['schema_version'] == 'candidate_reranker_training_workflow_v2'
    assert receipt['semantic_feature_contract_sha256'] == bundle['semantic_feature_contract_sha256']
    manifest = json.loads(Path(receipt['model_manifest']['path']).read_bytes())
    report = json.loads(Path(receipt['training_report']['path']).read_bytes())
    assert manifest['model']['schema_version'].endswith('_v2') and manifest['feature_schema'].endswith('_v2')
    assert manifest['schema_version'] == ('candidate_reranker_manifest_v3' if backend == workflow.NIL_BACKEND else 'candidate_reranker_manifest_v2')
    assert manifest['model']['training_binding'] == report['training_binding']
    assert receipt['semantic_inputs_sha256'] == report['training_binding']['semantic_inputs_sha256']
    assert report['model_sha256'] == sha(raw_json(manifest['model']))
    scorer = load_scorer(receipt['model_manifest']['path'], expected_sha256=receipt['model_manifest']['sha256'])
    assert scorer.summary() == receipt['scorer_summary']
    assert scorer.summary()['semantic_input_required'] is True
    assert scorer.summary()['semantic_contract_sha256'] == bundle['semantic_feature_contract_sha256']
    loaded = workflow.read_training_bundle(path, expected_sha256=expected)
    artifact = _artifact((bundle['split_manifest'], loaded['source_payloads'], loaded['evidence_payloads'], bundle['examples']))
    scored = scorer.score(bundle['examples'][0]['frozen_view'], semantic_input=artifact,
                          evidence_payloads=loaded['evidence_payloads'])
    assert scored['status'] == 'SCORED_LEARNED'
    assert scored['probability_status'] == 'NOT_AVAILABLE_UNCALIBRATED'
    if backend == workflow.NIL_BACKEND:
        assert scored['event_logits'][-1]['label'] == '__NIL__' and scored['nil_probability'] is None
    assert receipt['calibration_executed'] is receipt['actual_performance_evaluated'] is False
    assert receipt['formal_kpi_status'] == 'NOT_ESTIMABLE'
    assert {str(p): p.read_bytes() for p in path.parent.rglob('*') if p.is_file()} == before
    with pytest.raises(ValueError, match='새 경로'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')


@pytest.mark.parametrize('fault', ['missing_pin', 'wrong_pin', 'missing_backend', 'v2_with_semantic_pin'])
def test_semantic_bundle_optin_and_policy_are_explicit_before_optimizer(tmp_path, monkeypatch, fault):
    from src.llm_batch.grounding import candidate_reranker_nil_learned as learned
    path, _, bundle = semantic_bundle(tmp_path / 'input')
    if fault == 'missing_pin':
        bundle.pop('semantic_feature_contract_sha256')
    elif fault == 'wrong_pin':
        bundle['semantic_feature_contract_sha256'] = '0' * 64
    elif fault == 'missing_backend':
        bundle.pop('backend')
    else:
        bundle['schema_version'] = workflow.BUNDLE_V2_SCHEMA
    expected = replace_bundle(path, bundle)
    monkeypatch.setattr(learned, 'train_model', lambda *a, **k: pytest.fail('invalid bundle reached optimizer'))
    with pytest.raises(ValueError):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=tmp_path / 'trained')
    assert not (tmp_path / 'trained').exists()


def test_semantic_readback_policy_mismatch_has_no_success_receipt(tmp_path, monkeypatch):
    from src.llm_batch.grounding import candidate_reranker_shadow as shadow
    path, expected, _ = semantic_bundle(tmp_path / 'input')
    original = shadow.load_scorer
    def changed(*args, **kwargs):
        summary = original(*args, **kwargs).summary()
        summary['semantic_contract_sha256'] = '0' * 64
        class WrongPolicy:
            def summary(self):
                return summary
        return WrongPolicy()
    monkeypatch.setattr(shadow, 'load_scorer', changed)
    output = tmp_path / 'trained'
    with pytest.raises(ValueError, match='정책 재판독 불일치'):
        workflow.train_bundle(bundle_path=path, expected_sha256=expected, output_dir=output)
    assert (output / 'model_manifest.json').is_file() and not (output / 'workflow_receipt.json').exists()
