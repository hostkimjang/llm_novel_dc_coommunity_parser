from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.llm_batch.measurement.recovery_execution_readback import build_recovery_execution_readback
from src.llm_batch.monitor.recovery_view import publish_recovery_view, read_recovery_view
from tests.recovery_execution_fixtures import build_bound_fixture, json_bytes


def attach(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    report = build_recovery_execution_readback(bundle['bound'])
    path = bundle['bound'].output_dir / 'reports' / 'readback.json'
    path.parent.mkdir(parents=True)
    path.write_bytes(json_bytes(report))
    ref = publish_recovery_view(bundle['bound'], path, root=tmp_path)
    return bundle, report, path, Path(ref['path'])


def test_attach_preserves_originals_and_live_history_show_same_bound_report(tmp_path, monkeypatch):
    bundle, report, path, target = attach(tmp_path)
    from src.llm_batch.monitor import server
    monkeypatch.setattr(server, '_OUT_DIR', tmp_path)
    result = Path(bundle['artifact_refs']['result']['path'])
    original = {key: Path(ref['path']).read_bytes() for key, ref in bundle['artifact_refs'].items()}
    live = server._to_live_detail(bundle['result'], output_path=result)
    history = server._history_item(bundle['result'], SimpleNamespace(path=result, manifest=Path(bundle['artifact_refs']['manifest']['path'])))
    assert live['recovery_execution'] == history['recovery_execution']
    view = live['recovery_execution']
    assert view['binding_status'] == 'BOUND' and view['report'] == report
    assert view['verification_scope'] == 'FILE_AND_BASE_BINDING_ONLY'
    assert view['report']['execution_status'] == 'NOT_STARTED'
    assert view['report']['actual_external_call_count'] == 0
    assert view['report']['tokens'] is None
    assert {key: Path(ref['path']).read_bytes() for key, ref in bundle['artifact_refs'].items()} == original
    assert publish_recovery_view(bundle['bound'], path, root=tmp_path)['path'] == str(target)


def test_no_companion_does_not_create_files(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    before = sorted(str(p) for p in tmp_path.rglob('*'))
    view = read_recovery_view(bundle['artifact_refs']['result']['path'], tmp_path, item=bundle['result'])
    assert view['binding_status'] == 'MISSING'
    assert sorted(str(p) for p in tmp_path.rglob('*')) == before


@pytest.mark.parametrize('change', ['row', 'report', 'manifest', 'result', 'companion', 'wrong_result', 'outside_report', 'self_hash'])
def test_corrupt_or_foreign_references_never_show_success(tmp_path, change):
    bundle, report, report_path, target = attach(tmp_path)
    output = Path(bundle['artifact_refs']['result']['path'])
    item = deepcopy(bundle['result'])
    reference = json.loads(target.read_bytes())
    if change == 'row':
        item['title'] = '다른 결과'
    elif change == 'report':
        report_path.write_bytes(b'{}')
    elif change in ('manifest', 'result'):
        Path(bundle['artifact_refs'][change]['path']).write_bytes(b'{}')
    elif change == 'companion':
        target.write_bytes(b'{')
    else:
        if change == 'wrong_result':
            reference['result']['path'] = bundle['artifact_refs']['router']['path']
        elif change == 'outside_report':
            reference['report']['path'] = str(tmp_path.parent / 'outside.json')
        elif change == 'self_hash':
            report['execution_status'] = 'COMPLETED_SIMULATION'
            raw = json_bytes(report)
            report_path.write_bytes(raw)
            reference['report'].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        target.write_bytes(json_bytes(reference))
    view = read_recovery_view(output, tmp_path, item=item)
    assert view['binding_status'] == 'INVALID'
    assert 'report' not in view


@pytest.mark.parametrize('identifier', [102, '101', True])
def test_other_row_or_typed_id_is_unplanned_not_failed(tmp_path, identifier):
    bundle, _, _, _ = attach(tmp_path)
    item = {**bundle['result'], 'post_id': identifier}
    view = read_recovery_view(bundle['artifact_refs']['result']['path'], tmp_path, item=item)
    assert view['binding_status'] == 'NO_PLAN_PROVIDED' and 'report' not in view


def test_existing_companion_is_not_overwritten(tmp_path):
    bundle, _, path, target = attach(tmp_path)
    target.write_bytes(b'{"historical":true}')
    with pytest.raises(ValueError, match='이미 다른'):
        publish_recovery_view(bundle['bound'], path, root=tmp_path)
    assert target.read_bytes() == b'{"historical":true}'


def test_linked_report_rejected_without_reading_target(tmp_path):
    bundle, _, path, target = attach(tmp_path)
    # Windows에서도 관리자 권한이 필요 없는 hardlink로 경계 확인.
    linked = path.with_name('linked.json')
    import os
    os.link(path, linked)
    view = read_recovery_view(bundle['artifact_refs']['result']['path'], tmp_path, item=bundle['result'])
    assert view['binding_status'] == 'INVALID'
    with pytest.raises(ValueError):
        publish_recovery_view(bundle['bound'], path, root=tmp_path)


def test_reader_does_not_rebuild_journal_or_read_hmac(tmp_path, monkeypatch):
    bundle, _, _, _ = attach(tmp_path)
    import src.llm_batch.monitor.recovery_view as module
    monkeypatch.setattr(module, 'validate_recovery_execution_readback', lambda *a, **k: pytest.fail('GET must not revalidate or execute'))
    assert read_recovery_view(bundle['artifact_refs']['result']['path'], tmp_path, item=bundle['result'])['binding_status'] == 'BOUND'


def test_history_batch_reads_companion_once_then_binds_each_row(tmp_path, monkeypatch):
    bundle, _, _, _ = attach(tmp_path)
    from src.llm_batch.monitor import server
    monkeypatch.setattr(server, '_OUT_DIR', tmp_path)
    record = SimpleNamespace(path=Path(bundle['artifact_refs']['result']['path']), manifest=None)
    rows = [bundle['result'], {**bundle['result'], 'post_id': 102}]
    monkeypatch.setattr(server, '_history_record', lambda _: (record, None))
    monkeypatch.setattr(server, '_load_result_file', lambda _: rows)
    calls = []
    original = server.read_recovery_view
    def reader(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(server, 'read_recovery_view', reader)
    response = server._history_detail('key', 0, 200, False)
    items = json.loads(response.body)
    assert len(calls) == 1
    assert [item['recovery_execution']['binding_status'] for item in items] == ['BOUND', 'NO_PLAN_PROVIDED']


@pytest.mark.parametrize('manifest', [[], None, True, 'foreign'])
def test_non_object_manifest_with_matching_file_hash_returns_invalid(tmp_path, manifest):
    bundle, _, _, target = attach(tmp_path)
    reference = json.loads(target.read_bytes())
    raw = json_bytes(manifest)
    Path(reference['manifest']['path']).write_bytes(raw)
    reference['manifest'].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    target.write_bytes(json_bytes(reference))
    assert read_recovery_view(bundle['artifact_refs']['result']['path'], tmp_path,
                              item=bundle['result'])['binding_status'] == 'INVALID'
