"""명시 provider 진입점과 현재 원본에 결속된 표시. 전송은 MockTransport만 사용한다."""
import builtins
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import expert_main
from src.llm_batch.measurement.recovery_provider_readback import build_provider_report
from src.llm_batch.monitor import recovery_provider_view as view_module
from src.llm_batch.monitor.recovery_provider_view import publish_recovery_provider_view, read_recovery_provider_view
from src.llm_batch.runtime.recovery_provider_transport import RecoveryProviderRunner
from tests.recovery_provider_fixtures import build_recovery_provider_fixture
from tests.recovery_execution_fixtures import json_bytes


@pytest.fixture(autouse=True)
def no_network_and_measurement(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('external socket forbidden'))
    for key in list(os.environ):
        if key.startswith(('PIPELINE_MEASUREMENT_', 'PIPELINE_PAIRED_EXECUTION_')):
            monkeypatch.delenv(key)
    monkeypatch.delenv('EXPERT_EXECUTION_PROFILE', raising=False)


def attach(tmp_path, *, dispatched=False):
    bundle = build_recovery_provider_fixture(tmp_path)
    bound = bundle['bound']
    calls = []
    if dispatched:
        class Body(httpx.SyncByteStream):
            def __iter__(self):
                yield json_bytes({'query': bound.payload['query'],
                    'results': [{'title': '합성 검색 응답', 'url': 'https://example.invalid/detail/1'}], 'total': 1})
        def answer(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, stream=Body())
        runner = RecoveryProviderRunner(binding=bound.binding, policy=bound.policy,
            requests=bound.requests, journal_path=bound.journal_path, endpoints=bound.endpoints,
            source_check=bound.verify_protected_sources, cancelled=lambda: False,
            test_transport=httpx.MockTransport(answer), clock_ms=lambda: 0)
        receipt = runner.request('MCP_SEARCH', bound.payload, request_id=bound.requests[0]['request_id'])
        assert receipt['status'] == 'SUCCESS', receipt
    report = build_provider_report(bound)
    path = bound.output_dir / 'reports' / 'provider.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(json_bytes(report))
    reference = publish_recovery_provider_view(bound, path, root=tmp_path)
    return bundle, report, path, Path(reference['path']), calls


def test_real_report_and_live_history_preserve_sources_and_guard_boundary(tmp_path, monkeypatch):
    bundle, report, path, target, calls = attach(tmp_path, dispatched=True)
    from src.llm_batch.monitor import server
    monkeypatch.setattr(server, '_OUT_DIR', tmp_path)
    refs = bundle['source_refs']
    original = {role: Path(ref['path']).read_bytes() for role, ref in refs.items()}
    output = Path(refs['result']['path'])
    live = server._to_live_detail(bundle['result'], output_path=output)
    history = server._history_item(bundle['result'], SimpleNamespace(path=output, manifest=Path(refs['manifest']['path'])))
    assert len(calls) == 1 and calls[0] == bundle['bound'].payload
    assert live['recovery_provider_execution'] == history['recovery_provider_execution']
    view = live['recovery_provider_execution']
    assert view['binding_status'] == 'BOUND' and view['report'] == report
    assert report['execution_status'] == 'PROVIDER_EVIDENCE_STORED'
    assert report['guard_status'] == 'GUARD_NOT_EVALUATED'
    assert report['actual_external_call_count'] == 0 and report['client_http_invocations'] == 1
    assert report['remote_provider_dispatch_count'] is None
    assert report['data_kind'] == 'TEST_SYNTHETIC' and report['transport_mode'] == 'TEST_DOUBLE'
    assert all(report[key] is False for key in ('public_apply', 'publication_authority', 'central_db_write'))
    assert report['base']['export_run_id'] != report['base']['base_attempt_run_id']
    assert live['recovery_execution']['binding_status'] == 'MISSING'
    assert publish_recovery_provider_view(bundle['bound'], path, root=tmp_path)['path'] == str(target)
    assert {role: Path(ref['path']).read_bytes() for role, ref in refs.items()} == original


def test_missing_provider_companion_is_read_only_and_does_not_reuse_simulation(tmp_path):
    bundle = build_recovery_provider_fixture(tmp_path)
    output = Path(bundle['source_refs']['result']['path'])
    output.with_name(output.stem + '_recovery_view.json').write_bytes(b'{"legacy_simulation":true}')
    before = sorted(str(path) for path in tmp_path.rglob('*'))
    result = read_recovery_provider_view(output, tmp_path, item=bundle['result'])
    assert result['binding_status'] == 'MISSING' and 'report' not in result
    assert sorted(str(path) for path in tmp_path.rglob('*')) == before


@pytest.mark.parametrize('change', ['row', 'result', 'manifest', 'report', 'companion',
    'self_sha', 'wrong_result', 'outside_report', 'export_run', 'source_scope', 'not_finalized'])
def test_tampered_or_foreign_provider_refs_fail_closed(tmp_path, change):
    bundle, report, report_path, target, _ = attach(tmp_path)
    ref = json.loads(target.read_bytes())
    item = deepcopy(bundle['result'])
    if change == 'row':
        item['title'] = '다른 행'
    elif change in ('result', 'manifest'):
        Path(bundle['source_refs'][change]['path']).write_bytes(b'{}')
    elif change == 'report':
        report_path.write_bytes(b'{}')
    elif change == 'companion':
        target.write_bytes(b'{')
    else:
        if change == 'self_sha':
            report['guard_status'] = 'APPROVED'
            raw = json_bytes(report)
            report_path.write_bytes(raw)
            ref['report'].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        elif change == 'wrong_result':
            ref['result']['path'] = bundle['source_refs']['router']['path']
        elif change == 'outside_report':
            ref['report']['path'] = str(tmp_path.parent / 'outside.json')
        else:
            manifest = deepcopy(bundle['manifest'])
            field, value = {'export_run': ('run_id', report['base']['base_attempt_run_id']),
                'source_scope': ('publication_scope_id', 'foreign'), 'not_finalized': ('terminal_artifacts_finalized', False)}[change]
            manifest[field] = value
            raw = json_bytes(manifest)
            Path(ref['manifest']['path']).write_bytes(raw)
            ref['manifest'].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        target.write_bytes(json_bytes(ref))
    view = read_recovery_provider_view(bundle['source_refs']['result']['path'], tmp_path, item=item)
    assert view['binding_status'] == 'INVALID' and 'report' not in view


@pytest.mark.parametrize('identifier', [202, '101', True])
def test_other_row_and_post_id_type_have_no_plan(tmp_path, identifier):
    bundle, _, _, _, _ = attach(tmp_path)
    row = {**bundle['result'], 'post_id': identifier}
    view = read_recovery_provider_view(bundle['source_refs']['result']['path'], tmp_path, item=row)
    assert view['binding_status'] == 'NO_PLAN_PROVIDED' and 'report' not in view


def test_existing_companion_and_linked_report_are_never_overwritten(tmp_path):
    bundle, _, report_path, target, _ = attach(tmp_path)
    before = target.read_bytes()
    os.link(report_path, report_path.with_name('linked.json'))
    assert read_recovery_provider_view(bundle['source_refs']['result']['path'], tmp_path)['binding_status'] == 'INVALID'
    with pytest.raises(ValueError):
        publish_recovery_provider_view(bundle['bound'], report_path, root=tmp_path)
    assert target.read_bytes() == before


def test_different_existing_companion_is_not_overwritten(tmp_path):
    bundle, _, path, target, _ = attach(tmp_path)
    target.write_bytes(b'{"historical_provider_reference":true}')
    with pytest.raises(ValueError, match='이미 다른'):
        publish_recovery_provider_view(bundle['bound'], path, root=tmp_path)
    assert target.read_bytes() == b'{"historical_provider_reference":true}'


def test_resealed_claim_is_rebuilt_before_publishing(tmp_path):
    bundle = build_recovery_provider_fixture(tmp_path)
    report = build_provider_report(bundle['bound'])
    # schema와 self SHA만 맞춰도 저장 원장에 없는 실행을 publisher가 승인하면 안 된다.
    report['budget']['reservations_consumed'] = 1
    report['report_sha256'] = view_module.canonical_sha256({k: v for k, v in report.items() if k != 'report_sha256'})
    path = bundle['bound'].output_dir / 'forged.json'
    path.parent.mkdir(parents=True)
    path.write_bytes(json_bytes(report))
    with pytest.raises(ValueError):
        publish_recovery_provider_view(bundle['bound'], path, root=tmp_path)
    output = Path(bundle['source_refs']['result']['path'])
    assert not output.with_name(output.stem + '_recovery_provider_view.json').exists()


def test_get_does_not_rebuild_journal_or_read_source_key(tmp_path, monkeypatch):
    bundle, _, _, _, _ = attach(tmp_path)
    from src.llm_batch.measurement import recovery_provider_readback as reader
    monkeypatch.setattr(reader, 'build_provider_report', lambda *a, **k: pytest.fail('GET must not rebuild'))
    assert read_recovery_provider_view(bundle['source_refs']['result']['path'], tmp_path,
        item=bundle['result'])['binding_status'] == 'BOUND'


def test_history_batch_reads_provider_companion_once(tmp_path, monkeypatch):
    bundle, _, _, _, _ = attach(tmp_path)
    from src.llm_batch.monitor import server
    monkeypatch.setattr(server, '_OUT_DIR', tmp_path)
    record = SimpleNamespace(path=Path(bundle['source_refs']['result']['path']), manifest=Path(bundle['source_refs']['manifest']['path']))
    monkeypatch.setattr(server, '_history_record', lambda _: (record, None))
    monkeypatch.setattr(server, '_load_result_file', lambda _: bundle['results'])
    calls, original = [], server.read_recovery_provider_view
    def read(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(server, 'read_recovery_provider_view', read)
    rows = json.loads(server._history_detail('key', 0, 200, False).body)
    assert calls == [1]
    assert [row['recovery_provider_execution']['binding_status'] for row in rows] == ['BOUND', 'NO_PLAN_PROVIDED']


def provider_argv():
    return ['--recovery-provider-plan', 'pinned.json', '--recovery-provider-plan-sha256', 'a' * 64,
            '--recovery-hmac-key-file', 'existing.hex', '--recovery-attempt-id', 'attempt',
            '--recovery-session-id', 'session']


def test_main_provider_routes_once_before_normal_or_simulation_work(monkeypatch, capsys, tmp_path):
    from tools import run_recovery_provider as workflow
    from tools import run_recovery_simulation as simulation
    calls = []
    def run(**kwargs):
        calls.append(kwargs)
        return {'execution_status': 'PROVIDER_EVIDENCE_STORED', 'guard_status': 'GUARD_NOT_EVALUATED'}
    monkeypatch.setattr(workflow, 'run_recovery_provider', run)
    monkeypatch.setattr(simulation, 'run_recovery_simulation', lambda **k: pytest.fail('simulation mixed'))
    monkeypatch.setattr(expert_main, '__file__', str(tmp_path / 'expert_main.py'))
    monkeypatch.setattr(expert_main, '_CLI_ARGS', expert_main._parse_args(provider_argv()))
    monkeypatch.setattr(expert_main, 'load_jsonl_posts', lambda *a, **k: pytest.fail('normal input read'))
    monkeypatch.setattr(expert_main, '_configure_mcp_endpoints', lambda *a, **k: pytest.fail('normal MCP setup'))
    expert_main.main()
    assert calls == [{'plan_path': 'pinned.json', 'plan_sha256': 'a' * 64,
        'hmac_key_path': 'existing.hex', 'attempt_id': 'attempt', 'session_id': 'session', 'root': tmp_path / 'out'}]
    assert json.loads(capsys.readouterr().out)['guard_status'] == 'GUARD_NOT_EVALUATED'


@pytest.mark.parametrize('extra', [['input.jsonl'], ['--input', 'input.jsonl'], ['--output', 'out.json'],
    ['--no-dashboard'], ['--parallel', '1'], ['--execution-profile', 'low-load-validation'],
    ['--llm-model', 'model'], ['--recovery-simulation-plan', 'simulation.json'], ['--recovery-unknown', 'x']])
def test_provider_main_rejects_mixed_arguments_without_workflow(monkeypatch, extra):
    from tools import run_recovery_provider as workflow
    monkeypatch.setattr(workflow, 'run_recovery_provider', lambda **k: pytest.fail('must not execute'))
    monkeypatch.setattr(expert_main, '_CLI_ARGS', expert_main._parse_args(provider_argv() + extra))
    with pytest.raises(ValueError):
        expert_main.main()


@pytest.mark.parametrize('removed', range(5))
def test_provider_requires_all_five_options(removed):
    arguments = provider_argv()
    del arguments[2 * removed:2 * removed + 2]
    with pytest.raises(ValueError):
        args = expert_main._parse_args(arguments)
        result = expert_main._resolve_recovery_provider_options(args, {})
        if result is None:
            expert_main._resolve_recovery_simulation_options(args, {})


@pytest.mark.parametrize('value', ['', 'A' * 64, 'a' * 63, '../plan', ' a' + 'a' * 63])
def test_provider_pin_format_rejected(value):
    argv = provider_argv(); argv[3] = value
    with pytest.raises(ValueError):
        expert_main._resolve_recovery_provider_options(expert_main._parse_args(argv), {})


@pytest.mark.parametrize('key,value', [
    ('PIPELINE_MEASUREMENT_EXECUTION_MODE', 'FRESH_EXECUTION_REQUIRED'),
    ('PIPELINE_MEASUREMENT_EXECUTION_MODE', 'FRESH_SEMANTIC_OBSERVATION_REQUIRED'),
    ('PIPELINE_MEASUREMENT_RUN_SPEC_SHA256', 'a' * 64),
    ('PIPELINE_PAIRED_EXECUTION_POLICY_PATH', 'policy.json'), ('EXPERT_EXECUTION_PROFILE', 'paired-measurement')])
def test_provider_rejects_fresh_or_paired_environment(key, value):
    with pytest.raises(ValueError, match='계측|paired'):
        expert_main._resolve_recovery_provider_options(expert_main._parse_args(provider_argv()), {key: value})


def test_provider_off_reaches_original_setup_without_workflow_import(monkeypatch):
    from llm_batch.runtime import execution_config
    class NormalSetupReached(Exception):
        pass
    def normal(*a, **k):
        raise NormalSetupReached()
    monkeypatch.setattr(execution_config, 'resolve_execution_settings', normal)
    monkeypatch.setattr(expert_main, '_CLI_ARGS', expert_main._parse_args([]))
    original_import = builtins.__import__
    def import_without_recovery(name, *a, **k):
        assert name not in {'tools.run_recovery_provider', 'tools.run_recovery_simulation'}
        return original_import(name, *a, **k)
    monkeypatch.setattr(builtins, '__import__', import_without_recovery)
    with pytest.raises(NormalSetupReached):
        expert_main.main()
