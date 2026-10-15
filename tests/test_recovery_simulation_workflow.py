"""실제 main→합성 executor→독립 판독→companion 결속. HTTP 경계만 대체한다."""
from copy import deepcopy
import builtins
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import expert_main
from src.llm_batch.ledger.private_file import create_private_file
from src.llm_batch.measurement.recovery_execution_contract import (
    bind_recovery_execution_plan, build_recovery_execution_plan,
)
from src.llm_batch.monitor.recovery_view import read_recovery_view
from tests.recovery_execution_fixtures import build_bound_fixture, json_bytes
from tools import run_recovery_simulation as workflow


class Clock:
    def __init__(self):
        self.value = 1000

    def monotonic_ms(self):
        return self.value

    def sleep_ms(self, value):
        self.value += value


def make_dashboard_fixture(root: Path, **kwargs) -> dict:
    """새 합성 자료만 생성한다. root 브라우저 검증에서도 재사용할 수 있는 배열 결과다."""
    root = Path(root).resolve()
    with patch('tests.recovery_execution_fixtures.HMAC_KEY', b'k' * 32):
        bundle = build_bound_fixture(root / 'seed', **kwargs)
    raw, refs = deepcopy(bundle['artifact_bytes']), deepcopy(bundle['artifact_refs'])
    result_path = root / 'expert_result_20261010_120000_99999.json'
    manifest_path = result_path.with_name(result_path.stem + '_manifest.json')
    manifest = {**bundle['manifest'], 'output_file': str(result_path), 'completed_count': 1,
                'input_post_count': len(bundle['input_records']), 'terminal_artifacts_finalized': True,
                'execution_mode': 'LOCAL_SIMULATION_ONLY'}
    raw['result'], raw['manifest'] = json_bytes([bundle['result']]), json_bytes(manifest)
    for role, path in (('result', result_path), ('manifest', manifest_path)):
        with path.open('xb') as stream:
            stream.write(raw[role])
        refs[role] = {'path': str(path), 'sha256': hashlib.sha256(raw[role]).hexdigest(), 'bytes': len(raw[role])}
    arguments = {**bundle['build_kwargs'], 'artifact_refs': refs, 'artifact_bytes': raw,
                 'result_pointer': '/0', 'output_dir': str(root / 'recovery_output')}
    plan = build_recovery_execution_plan(**arguments)
    bound = bind_recovery_execution_plan(plan, hmac_key=bundle['hmac_key'])
    plan_path, key_path = root / 'recovery_plan.json', root / 'existing_audit_key.hex'
    with plan_path.open('xb') as stream:
        stream.write(json_bytes(plan))
    with os.fdopen(create_private_file(key_path), 'wb') as stream:
        stream.write((bundle['hmac_key'].hex() + '\n').encode('ascii'))
    return {**bundle, 'plan': plan, 'bound': bound, 'manifest': manifest,
            'artifact_refs': refs, 'artifact_bytes': raw, 'build_kwargs': arguments,
            'plan_path': plan_path, 'key_path': key_path, 'root': root}


def invoke(bundle, **overrides):
    args = dict(plan_path=bundle['plan_path'], hmac_key_path=bundle['key_path'],
                attempt_id='recovery-1', session_id='simulation-session', root=bundle['root'], clock=Clock())
    args.update(overrides)
    return workflow.run_recovery_simulation(**args)


def original_bytes(bundle):
    return {str(path): path.read_bytes() for path in [bundle['plan_path'], bundle['key_path'],
        *(Path(ref['path']) for ref in bundle['artifact_refs'].values())]}


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('socket call is forbidden'))
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: pytest.fail('socket call is forbidden'))
    for key in list(os.environ):
        if key.startswith('PIPELINE_MEASUREMENT_') or key.startswith('PIPELINE_PAIRED_EXECUTION_'):
            monkeypatch.delenv(key)
    monkeypatch.delenv('EXPERT_EXECUTION_PROFILE', raising=False)
    monkeypatch.setenv('DASHBOARD_URL', 'http://127.0.0.1:8080')


@pytest.fixture
def dashboard(monkeypatch):
    calls = []
    def health(url):
        calls.append(url)
        return {'url': url, 'pid': 42, 'service': 'expert-pipeline-monitor', 'standalone': True}
    monkeypatch.setattr(workflow, '_dashboard_health', health)
    return calls


def test_real_workflow_preserves_sources_and_replay_dispatches_zero(tmp_path, dashboard):
    bundle = make_dashboard_fixture(tmp_path, post_ids=[101, '202', 303])
    before = original_bytes(bundle)
    result = invoke(bundle)
    assert result['execution_status'] == 'COMPLETED_SIMULATION'
    assert result['verification_status'] == 'VERIFIED_LOCAL_CONTRACT'
    assert result['execution_mode'] == 'LOCAL_SIMULATION_ONLY'
    assert result['dispatches_this_invocation'] == 1 and not result['replayed']
    assert result['actual_external_call_count'] == 0 and result['public_apply'] is False
    assert result['formal_kpi_status'] == 'NOT_ESTIMABLE'
    assert result['dashboard']['status'] == 'CONNECTED_STANDALONE'
    assert result['dashboard']['visibility_verified'] is False and len(dashboard) == 2
    assert result['execution_profile'] == 'low-load-validation'
    assert result['resources_start']['pid'] == result['resources_end']['pid'] == os.getpid()
    assert result['resources_start']['logical_cpu_count'] == result['resources_end']['logical_cpu_count'] == 1
    assert all(value == '1' for value in result['resources_end']['numeric_threads'].values())
    if os.name == 'nt':
        assert result['resources_end']['priority_class'] == 16384 and result['resources_end']['affinity_mask'] == 2
    saved_receipt = json.loads(Path(result['workflow_receipt']['path']).read_bytes())
    expected_body = {key: value for key, value in result.items() if key not in result['receipt_hash_excludes']}
    assert saved_receipt['receipt_sha256'] == result['receipt_sha256'] == hashlib.sha256(json_bytes(expected_body)).hexdigest()
    report = json.loads(Path(result['reports'][0]['path']).read_bytes())
    assert report['input_count'] == 3 and report['attempt_count'] == 1
    assert [row['state'] for row in report['input_rows']] == ['COMPLETED_SIMULATION', 'NO_PLAN_PROVIDED', 'NO_PLAN_PROVIDED']
    view = read_recovery_view(bundle['artifact_refs']['result']['path'], tmp_path, item=bundle['result'])
    assert view['binding_status'] == 'BOUND' and view['report'] == report
    preserved = {str(path): path.read_bytes() for path in [bundle['bound'].journal_path,
        *(Path(ref['path']) for ref in result['reports']), Path(result['dashboard_reference']['path'])]}
    replay = invoke(bundle)
    assert replay['replayed'] and replay['dispatches_this_invocation'] == 0
    assert replay['reports'] == result['reports'] and replay['dashboard_reference'] == result['dashboard_reference']
    assert {path: Path(path).read_bytes() for path in preserved} == preserved
    assert original_bytes(bundle) == before


@pytest.mark.parametrize('failure', ['missing_key', 'raw_key', 'source_tamper', 'no_dashboard', 'outside_root', 'partial_report', 'foreign_companion'])
def test_preflight_failure_has_no_dispatch_or_new_journal(tmp_path, monkeypatch, dashboard, failure):
    bundle = make_dashboard_fixture(tmp_path)
    args = {}
    if failure == 'missing_key':
        args['hmac_key_path'] = tmp_path / 'missing_key'
    elif failure == 'raw_key':
        bundle['key_path'].write_bytes(b'k' * 32)
    elif failure == 'source_tamper':
        Path(bundle['artifact_refs']['manifest']['path']).write_bytes(b'{}')
    elif failure == 'no_dashboard':
        monkeypatch.setattr(workflow, '_dashboard_health', lambda _: (_ for _ in ()).throw(OSError('offline')))
    elif failure == 'outside_root':
        args['root'] = tmp_path / 'another_root'
    elif failure == 'partial_report':
        path = bundle['bound'].output_dir / 'reports' / (hashlib.sha256(b'recovery-1').hexdigest() + '.json')
        path.parent.mkdir(parents=True)
        path.write_bytes(b'{}')
    else:
        path = Path(bundle['artifact_refs']['result']['path'])
        path.with_name(path.stem + '_recovery_view.json').write_bytes(b'{}')
    before = original_bytes(bundle)
    with pytest.raises((ValueError, OSError)):
        invoke(bundle, **args)
    assert not bundle['bound'].journal_path.exists()
    assert not bundle['bound'].journal_path.with_suffix('.jsonl.lock').exists()
    assert original_bytes(bundle) == before
    assert not (tmp_path / 'missing_key').exists()


@pytest.mark.parametrize('change', ['different_attempt', 'different_session', 'corrupt_json', 'corrupt_md'])
def test_existing_reports_and_companion_are_never_overwritten(tmp_path, dashboard, change):
    bundle = make_dashboard_fixture(tmp_path)
    first = invoke(bundle)
    args = {}
    if change == 'different_attempt':
        args['attempt_id'] = 'recovery-2'
    elif change == 'different_session':
        args['session_id'] = 'other-session'
    else:
        Path(first['reports'][0 if change == 'corrupt_json' else 1]['path']).write_bytes(b'changed')
    paths = [bundle['bound'].journal_path, Path(first['dashboard_reference']['path']),
             *(Path(ref['path']) for ref in first['reports'])]
    before = {str(path): path.read_bytes() for path in paths}
    with pytest.raises(ValueError):
        invoke(bundle, **args)
    assert {str(path): path.read_bytes() for path in paths} == before


def test_dashboard_loss_after_export_is_error_and_saved_work_is_replayable(tmp_path, monkeypatch, dashboard):
    bundle = make_dashboard_fixture(tmp_path)
    count = 0
    def health(url):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('dashboard stopped')
        return {'url': url, 'pid': 42, 'service': 'expert-pipeline-monitor', 'standalone': True}
    monkeypatch.setattr(workflow, '_dashboard_health', health)
    with pytest.raises(OSError, match='stopped'):
        invoke(bundle)
    result = invoke(bundle)
    assert result['replayed'] and result['dispatches_this_invocation'] == 0


def recovery_argv(bundle=None):
    return ['--recovery-simulation-plan', str(bundle['plan_path']) if bundle else 'plan.json',
            '--recovery-hmac-key-file', str(bundle['key_path']) if bundle else 'private.hex',
            '--recovery-attempt-id', 'recovery-1', '--recovery-session-id', 'simulation-session']


def test_actual_main_uses_real_workflow_and_returns_before_normal_pipeline(tmp_path, monkeypatch, dashboard, capsys):
    bundle = make_dashboard_fixture(tmp_path / 'out')
    monkeypatch.setattr(expert_main, '__file__', str(tmp_path / 'expert_main.py'))
    monkeypatch.setattr(expert_main, '_CLI_ARGS', expert_main._parse_args(recovery_argv(bundle)))
    monkeypatch.setattr(expert_main, 'load_jsonl_posts', lambda *a, **k: pytest.fail('normal input read'))
    monkeypatch.setattr(expert_main, '_configure_mcp_endpoints', lambda *a, **k: pytest.fail('MCP setup'))
    monkeypatch.setattr(expert_main, '_initialize_recovery_activation_runtime', lambda *a, **k: pytest.fail('key creation'))
    execute = workflow.execute_recovery_simulation
    monkeypatch.setattr(workflow, 'execute_recovery_simulation', lambda *a, **k: execute(*a, **{**k, 'clock': Clock()}))
    expert_main.main()
    result = json.loads(capsys.readouterr().out)
    assert result['execution_status'] == 'COMPLETED_SIMULATION'
    assert Path(result['dashboard_reference']['path']).is_file()
    assert len(dashboard) == 2


@pytest.mark.parametrize('arguments', [
    ['--recovery-hmac-key-file', 'key'], ['--recovery-attempt-id', 'x'],
    ['--recovery-session-id', 'x'], ['--recovery-simulation-plan', 'plan'],
    ['--recovery-typo', 'x'],
    recovery_argv() + ['input.jsonl'], recovery_argv() + ['--input', 'input.jsonl'],
    recovery_argv() + ['--output', 'output.json'], recovery_argv() + ['--no-dashboard'],
    recovery_argv() + ['--parallel', '1'], recovery_argv() + ['--llm-model', 'unused'],
    recovery_argv() + ['--candidate-retrieval', 'OFF'], recovery_argv() + ['--unknown', 'x'],
])
def test_actual_main_rejects_mixed_or_incomplete_recovery_before_any_work(monkeypatch, arguments):
    monkeypatch.setattr(expert_main, '_CLI_ARGS', expert_main._parse_args(arguments))
    monkeypatch.setattr(workflow, 'run_recovery_simulation', lambda **k: pytest.fail('workflow should not run'))
    monkeypatch.setattr(expert_main, 'load_jsonl_posts', lambda *a, **k: pytest.fail('normal input should not run'))
    with pytest.raises(ValueError):
        expert_main.main()


@pytest.mark.parametrize('key,value', [
    ('PIPELINE_MEASUREMENT_EXECUTION_MODE', 'FRESH_EXECUTION_REQUIRED'),
    ('PIPELINE_MEASUREMENT_EXECUTION_MODE', 'FRESH_SEMANTIC_OBSERVATION_REQUIRED'),
    ('PIPELINE_MEASUREMENT_RUN_SPEC_SHA256', 'a' * 64),
    ('EXPERT_EXECUTION_PROFILE', 'paired-measurement'),
])
def test_actual_main_rejects_fresh_environment(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    monkeypatch.setattr(expert_main, '_CLI_ARGS', expert_main._parse_args(recovery_argv()))
    monkeypatch.setattr(workflow, 'run_recovery_simulation', lambda **k: pytest.fail('fresh must not execute'))
    with pytest.raises(ValueError, match='계측|paired'):
        expert_main.main()


def test_off_main_reaches_original_setup_without_workflow_import_or_files(monkeypatch):
    from llm_batch.runtime import execution_config
    class NormalSetupReached(Exception):
        pass
    def normal_setup(*a, **k):
        raise NormalSetupReached()
    monkeypatch.setattr(execution_config, 'resolve_execution_settings', normal_setup)
    monkeypatch.setattr(expert_main, '_CLI_ARGS', expert_main._parse_args([]))
    original_import = builtins.__import__
    def tracked_import(name, *a, **k):
        assert name != 'tools.run_recovery_simulation'
        return original_import(name, *a, **k)
    monkeypatch.setattr(builtins, '__import__', tracked_import)
    monkeypatch.setattr(workflow, '_file', lambda *a, **k: pytest.fail('OFF must not read plan/key'))
    with pytest.raises(NormalSetupReached):
        expert_main.main()


@pytest.mark.parametrize('url', ['https://127.0.0.1:8080', 'http://example.com:8080',
    'http://127.0.0.1:8080/path', 'http://user@127.0.0.1:8080', 'http://127.0.0.1:8080?x=1',
    'http://127.0.0.1', 'http://127.0.0.1:99999'])
def test_dashboard_url_rejects_nonlocal_or_ambiguous_endpoint(url):
    with pytest.raises(ValueError):
        workflow._dashboard_url(url)


@pytest.mark.parametrize('change', ['none', 'service', 'standalone', 'ok', 'pid', 'redirect', 'size'])
def test_real_health_consumer_checks_service_and_disables_proxy_redirect(monkeypatch, change):
    payload = {'ok': True, 'service': 'expert-pipeline-monitor', 'standalone': True, 'pid': 42}
    if change in ('service', 'standalone', 'ok', 'pid'):
        payload[change] = {'service': 'other', 'standalone': False, 'ok': 1, 'pid': True}[change]
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def geturl(self):
            return 'http://127.0.0.1:8080/' + ('redirect' if change == 'redirect' else 'api/health')
        def read(self, count):
            assert count == 8193
            return b' ' * count if change == 'size' else json_bytes(payload)
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == 'http://127.0.0.1:8080/api/health' and timeout == 2
            return Response()
    def opener(*handlers):
        assert handlers[0].proxies == {} and isinstance(handlers[1], workflow._NoRedirect)
        return Opener()
    monkeypatch.setattr(workflow, 'build_opener', opener)
    if change == 'none':
        assert workflow._dashboard_health('http://127.0.0.1:8080')['pid'] == 42
    else:
        with pytest.raises(ValueError):
            workflow._dashboard_health('http://127.0.0.1:8080')
