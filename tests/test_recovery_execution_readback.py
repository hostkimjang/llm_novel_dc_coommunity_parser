from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.llm_batch.ledger.private_file import create_private_file
from src.llm_batch.ledger.recovery_execution_journal import FINALIZATION_ELAPSED_SCOPE, RecoveryExecutionJournal
from src.llm_batch.measurement.recovery_execution_contract import canonical_sha256, execution_journal_arguments
from src.llm_batch.measurement.recovery_execution_readback import (
    RecoveryExecutionReadbackError, build_recovery_execution_readback, read_strict_json,
    render_korean_report, validate_recovery_execution_readback,
)
from src.llm_batch.runtime.bounded_recovery import execute_recovery_simulation
from tests.recovery_execution_fixtures import build_bound_fixture, json_bytes
from tools.run_recovery_execution_readback import write_readback_reports


class Clock:
    def __init__(self):
        self.value = 1000

    def monotonic_ms(self):
        return self.value

    def sleep_ms(self, value):
        self.value += value


class Cancelled:
    def requested(self):
        return True


def journal_for(bundle):
    return RecoveryExecutionJournal(bundle['bound'].journal_path,
                                    **execution_journal_arguments(bundle['plan']))


def run(bundle, *, attempt='recovery-1', cancellation=None):
    return execute_recovery_simulation(bundle['bound'], fixture=bundle['fixture'],
        journal=journal_for(bundle), attempt_id=attempt, session_id='simulation-session',
        clock=Clock(), cancellation=cancellation)


def source_bytes(bundle):
    return {name: Path(ref['path']).read_bytes()
            for name, ref in bundle['artifact_refs'].items()}


def test_not_started_keeps_all_input_denominator_without_creating_files(tmp_path):
    bundle = build_bound_fixture(tmp_path, post_ids=[101, '202', 303])
    before = source_bytes(bundle)
    report = build_recovery_execution_readback(bundle['bound'])
    assert report['execution_status'] == 'NOT_STARTED'
    assert report['input_count'] == 3 and report['selected_base_count'] == 1
    assert report['attempt_count'] == 0 and report['consumed_simulated_dispatches'] == 0
    assert [row['state'] for row in report['input_rows']] == ['NOT_STARTED', 'NO_PLAN_PROVIDED', 'NO_PLAN_PROVIDED']
    assert report['input_rows'][1]['post_id'] == '202'
    assert not bundle['bound'].output_dir.exists()
    assert source_bytes(bundle) == before


def test_completed_output_events_fixture_and_sources_are_bound(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    before = source_bytes(bundle)
    result = run(bundle)
    assert result['status'] == 'COMPLETED_SIMULATION'
    report = build_recovery_execution_readback(bundle['bound'])
    assert report['verification_status'] == 'VERIFIED_LOCAL_CONTRACT'
    assert report['execution_status'] == 'COMPLETED_SIMULATION'
    assert report['consumed_simulated_dispatches'] == 1
    assert report['action_outcomes'] == {'SUCCESS': 1}
    assert report['pending_finalization_count'] == 0
    assert report['attempts'][0]['finalization_recorded'] is True
    assert report['budget_observation_scope'] == FINALIZATION_ELAPSED_SCOPE
    assert report['finalization_persistence_in_budget'] is False
    assert report['actual_external_call_count'] == 0
    assert report['tokens'] is None and report['price'] is None
    assert report['formal_kpi_status'] == 'NOT_ESTIMABLE'
    assert validate_recovery_execution_readback(report, bound_plan=bundle['bound']) == report
    assert '실제 검색·모델 호출' in render_korean_report(report)
    replayed = run(bundle)
    assert replayed['replayed'] is True and replayed['dispatches_this_invocation'] == 0
    assert build_recovery_execution_readback(bundle['bound']) == report
    assert source_bytes(bundle) == before


def test_transient_failure_stays_in_count_after_success(tmp_path):
    responses = [
        {'outcome': 'TRANSIENT_FAILURE', 'delay_ms': 1, 'retry_delay_ms': 2, 'response': None},
        {'outcome': 'SUCCESS', 'delay_ms': 1, 'retry_delay_ms': 0, 'response': {'saved': True}},
    ]
    bundle = build_bound_fixture(tmp_path, responses=responses)
    assert run(bundle)['status'] == 'COMPLETED_SIMULATION'
    report = build_recovery_execution_readback(bundle['bound'])
    assert report['consumed_simulated_dispatches'] == 2
    assert report['action_outcomes'] == {'SUCCESS': 1, 'TRANSIENT_FAILURE': 1}


@pytest.mark.parametrize('kind', ['budget', 'cancel', 'no_response', 'permanent_failure'])
def test_noncompletion_never_claims_success_or_drops_denominator(tmp_path, kind):
    options = {'policy_overrides': {'max_simulated_dispatches': 0}} if kind == 'budget' else {}
    if kind in {'no_response', 'permanent_failure'}:
        options['responses'] = [{'outcome': kind.upper(), 'delay_ms': 0, 'retry_delay_ms': 0, 'response': None}]
    bundle = build_bound_fixture(tmp_path, post_ids=[101, 202], **options)
    result = run(bundle, cancellation=Cancelled() if kind == 'cancel' else None)
    report = build_recovery_execution_readback(bundle['bound'])
    expected = {'budget': 'BUDGET_EXHAUSTED', 'cancel': 'CANCELLED',
                'no_response': 'INCOMPLETE', 'permanent_failure': 'FAILED'}[kind]
    assert result['status'] == report['execution_status'] == expected
    assert report['input_count'] == 2 and report['attempt_count'] == 1
    assert report['attempts'][0]['output'] is None
    assert report['consumed_simulated_dispatches'] == (0 if kind in {'budget', 'cancel'} else 1)


def test_reserved_crash_is_read_only_incomplete_not_unstarted(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    journal = journal_for(bundle)
    common = {'recovery_session_id': 'session', 'recovery_attempt_id': 'crashed-attempt', 'elapsed_ms': 0}
    journal.append(expected_head_sha256='GENESIS', event={**common, 'event_type': 'ATTEMPT_STARTED', 'payload': {}})
    action = execution_journal_arguments(bundle['plan'])['actions'][0]
    journal.append(expected_head_sha256=journal.snapshot()['head_sha256'], event={**common,
        'event_type': 'ACTION_RESERVED', 'payload': {**action, 'call_id': 'reserved-call',
            'reservation_ordinal': 1, 'retry_ordinal': 0, 'previous_call_id': None}})
    raw = journal.path.read_bytes()
    report = build_recovery_execution_readback(bundle['bound'])
    assert report['execution_status'] == 'INCOMPLETE' and report['open_call_count'] == 1
    assert report['consumed_simulated_dispatches'] == 1
    assert report['attempts'][0]['terminal_recorded'] is False
    assert journal.path.read_bytes() == raw


def test_corrupt_tail_is_not_repaired(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    run(bundle)
    path = bundle['bound'].journal_path
    corrupt = path.read_bytes() + b'{"unfinished":'
    path.write_bytes(corrupt)
    with pytest.raises(ValueError):
        build_recovery_execution_readback(bundle['bound'])
    assert path.read_bytes() == corrupt
    assert not path.with_name(path.name + '.tail_repair.jsonl').exists()


def test_output_raw_tamper_is_rejected(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    result = run(bundle)
    path = Path(result['output']['path'])
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(RecoveryExecutionReadbackError, match='SHA|크기'):
        build_recovery_execution_readback(bundle['bound'])


def test_resealed_output_and_journal_cannot_fabricate_fixture_response(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    result = run(bundle)
    path = Path(result['output']['path'])
    output = json.loads(path.read_bytes())
    invented = {'invented_success': True}
    response_raw = json_bytes(invented)
    response_sha = hashlib.sha256(response_raw).hexdigest()
    output['actions'][0].update(response=invented, response_sha256=response_sha, response_bytes=len(response_raw))
    output['receipt_sha256'] = canonical_sha256({key: value for key, value in output.items() if key != 'receipt_sha256'})
    raw = json_bytes(output) + b'\n'
    path.write_bytes(raw)
    events = [json.loads(line) for line in bundle['bound'].journal_path.read_bytes().splitlines()]
    previous = 'GENESIS'
    candidate_sha = None
    for event in events:
        if event['event_type'] == 'ACTION_TERMINAL':
            event['payload'].update(response_sha256=response_sha, response_bytes=len(response_raw))
        if event['event_type'] == 'ATTEMPT_TERMINAL':
            event['payload'].update(output_sha256=hashlib.sha256(raw).hexdigest(), output_bytes=len(raw))
        if event['event_type'] == 'ATTEMPT_FINALIZED':
            event['payload']['terminal_event_sha256'] = candidate_sha
        event['prev_event_sha256'] = previous
        event['event_sha256'] = canonical_sha256({key: value for key, value in event.items() if key != 'event_sha256'})
        previous = event['event_sha256']
        if event['event_type'] == 'ATTEMPT_TERMINAL':
            candidate_sha = previous
    bundle['bound'].journal_path.write_bytes(b''.join(json_bytes(event) + b'\n' for event in events))
    # 모든 checksum을 맞춰도 원래 선언형 fixture와의 모순을 검출해야 한다.
    journal_for(bundle).snapshot()
    with pytest.raises(RecoveryExecutionReadbackError, match='fixture'):
        build_recovery_execution_readback(bundle['bound'])


def test_alternate_journal_and_forged_report_are_rejected(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    with pytest.raises(RecoveryExecutionReadbackError, match='경로'):
        build_recovery_execution_readback(bundle['bound'], journal_path=tmp_path / 'different.jsonl')
    report = build_recovery_execution_readback(bundle['bound'])
    altered = deepcopy(report)
    altered['input_count'] += 1
    altered['report_sha256'] = canonical_sha256({key: value for key, value in altered.items() if key != 'report_sha256'})
    with pytest.raises(RecoveryExecutionReadbackError):
        validate_recovery_execution_readback(altered, bound_plan=bundle['bound'])


def test_valid_chain_and_output_cannot_turn_permanent_fixture_failure_into_retry(tmp_path):
    bundle = build_bound_fixture(tmp_path, responses=[
        {'outcome': 'PERMANENT_FAILURE', 'delay_ms': 0, 'retry_delay_ms': 0, 'response': None},
        {'outcome': 'SUCCESS', 'delay_ms': 0, 'retry_delay_ms': 0, 'response': {'second': True}},
    ])
    journal = journal_for(bundle)
    action = execution_journal_arguments(bundle['plan'])['actions'][0]
    common = {'recovery_session_id': 'synthetic-session', 'recovery_attempt_id': 'contradictory-attempt', 'elapsed_ms': 0}
    def append(kind, payload):
        return journal.append(expected_head_sha256=journal.snapshot()['head_sha256'],
                              event={**common, 'event_type': kind, 'payload': payload})
    append('ATTEMPT_STARTED', {})
    append('ACTION_RESERVED', {**action, 'call_id': 'call-1', 'reservation_ordinal': 1,
                               'retry_ordinal': 0, 'previous_call_id': None})
    # 원장의 상태·해시는 정상이어도 고정 응답은 영구 실패이므로 retry가 부당하다.
    append('ACTION_TERMINAL', {'call_id': 'call-1', 'outcome': 'TRANSIENT_FAILURE',
                               'response_sha256': None, 'response_bytes': 0})
    append('ACTION_RESERVED', {**action, 'call_id': 'call-2', 'reservation_ordinal': 2,
                               'retry_ordinal': 1, 'previous_call_id': 'call-1'})
    response = {'second': True}
    response_raw = json_bytes(response)
    response_sha = hashlib.sha256(response_raw).hexdigest()
    append('ACTION_TERMINAL', {'call_id': 'call-2', 'outcome': 'SUCCESS',
                               'response_sha256': response_sha, 'response_bytes': len(response_raw)})
    protected = bundle['bound'].verify_protected_sources()
    output = {'schema_version': 'recovery_simulation_output_v1', 'status': 'SIMULATION_OUTPUT_CANDIDATE',
              'execution_mode': 'LOCAL_SIMULATION_ONLY', 'data_kind': 'SYNTHETIC_CONTRACT_ONLY',
              'binding': execution_journal_arguments(bundle['plan'])['binding'],
              'recovery_session_id': common['recovery_session_id'], 'recovery_attempt_id': common['recovery_attempt_id'],
              'actions': [{**action, 'call_id': 'call-2', 'reservation_ordinal': 2, 'response': response,
                           'response_sha256': response_sha, 'response_bytes': len(response_raw)}],
              'protected_sources_start': protected, 'protected_sources_before_output': protected,
              'elapsed_ms_before_output_write': 0, 'actual_external_call_count': 0, 'public_apply': False,
              'publication_authority': False, 'central_db_write': False, 'tokens': None, 'price': None,
              'formal_kpi_status': 'NOT_ESTIMABLE'}
    output['receipt_sha256'] = canonical_sha256(output)
    raw = json_bytes(output) + b'\n'
    path = bundle['bound'].output_dir / 'attempts' / (hashlib.sha256(common['recovery_attempt_id'].encode()).hexdigest() + '.json')
    path.parent.mkdir()
    path.write_bytes(raw)
    candidate = append('ATTEMPT_TERMINAL', {'status': 'COMPLETED_SIMULATION', 'reason_codes': [],
                               'output_sha256': hashlib.sha256(raw).hexdigest(), 'output_bytes': len(raw)})
    append('ATTEMPT_FINALIZED', {'terminal_event_sha256': candidate['event_sha256'],
                                'status': 'COMPLETED_SIMULATION', 'reason_codes': [],
                                'budget_observation_scope': FINALIZATION_ELAPSED_SCOPE})
    journal.snapshot()  # 상태·해시 검산을 통과해도 fixture 결속의 모순은 남는다.
    with pytest.raises(RecoveryExecutionReadbackError, match='fixture'):
        build_recovery_execution_readback(bundle['bound'])


def test_completion_candidate_without_finalization_is_read_only_incomplete(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    run(bundle)
    path = bundle['bound'].journal_path
    events = [json.loads(line) for line in path.read_bytes().splitlines()]
    assert events[-1]['event_type'] == 'ATTEMPT_FINALIZED'
    raw = b''.join(json_bytes(event) + b'\n' for event in events[:-1])
    path.write_bytes(raw)
    report = build_recovery_execution_readback(bundle['bound'])
    attempt = report['attempts'][0]
    assert report['execution_status'] == 'INCOMPLETE' and report['pending_finalization_count'] == 1
    assert attempt['terminal_candidate_status'] == 'COMPLETED_SIMULATION'
    assert attempt['output'] is None and attempt['candidate_output'] is not None
    assert not attempt['finalization_recorded'] and path.read_bytes() == raw


def test_finalization_time_overrun_keeps_candidate_but_does_not_count_completion(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    run(bundle)
    path = bundle['bound'].journal_path
    events = [json.loads(line) for line in path.read_bytes().splitlines()]
    event = events[-1]
    assert event['event_type'] == 'ATTEMPT_FINALIZED'
    event['elapsed_ms'] = bundle['plan']['policy']['max_elapsed_ms'] + 1
    event['payload'].update(status='BUDGET_EXHAUSTED', reason_codes=['TERMINAL_DURABILITY_TIME_BUDGET_EXHAUSTED'])
    event['event_sha256'] = canonical_sha256({key: value for key, value in event.items() if key != 'event_sha256'})
    path.write_bytes(b''.join(json_bytes(item) + b'\n' for item in events))
    report = build_recovery_execution_readback(bundle['bound'])
    assert report['execution_status'] == 'BUDGET_EXHAUSTED'
    assert report['consumed_elapsed_ms'] == event['elapsed_ms']
    assert report['attempts'][0]['output'] is None
    assert report['attempts'][0]['candidate_output'] is not None


def test_cancellation_request_cannot_fabricate_fixture_confirmation(tmp_path):
    bundle = build_bound_fixture(tmp_path, responses=[
        {'outcome': 'SUCCESS', 'delay_ms': 20, 'retry_delay_ms': 0, 'response': {}}])
    journal = journal_for(bundle)
    action = execution_journal_arguments(bundle['plan'])['actions'][0]
    common = {'recovery_session_id': 'session', 'recovery_attempt_id': 'false-confirmation'}
    def append(kind, payload, elapsed):
        return journal.append(expected_head_sha256=journal.snapshot()['head_sha256'],
            event={**common, 'event_type': kind, 'payload': payload, 'elapsed_ms': elapsed})
    append('ATTEMPT_STARTED', {}, 0)
    append('ACTION_RESERVED', {**action, 'call_id': 'call', 'reservation_ordinal': 1,
                               'retry_ordinal': 0, 'previous_call_id': None}, 0)
    append('CANCEL_REQUESTED', {'reason_code': 'CANCEL_REQUESTED'}, 1)
    append('ACTION_TERMINAL', {'call_id': 'call', 'outcome': 'CANCEL_CONFIRMED',
                               'response_sha256': None, 'response_bytes': 0}, 2)
    candidate = append('ATTEMPT_TERMINAL', {'status': 'CANCELLED', 'reason_codes': [],
                                          'output_sha256': None, 'output_bytes': 0}, 3)
    append('ATTEMPT_FINALIZED', {'terminal_event_sha256': candidate['event_sha256'], 'status': 'CANCELLED',
                                'reason_codes': [], 'budget_observation_scope': FINALIZATION_ELAPSED_SCOPE}, 3)
    journal.snapshot()
    with pytest.raises(RecoveryExecutionReadbackError, match='fixture'):
        build_recovery_execution_readback(bundle['bound'])


def test_cli_only_writes_new_reports_and_preserves_original_key(tmp_path):
    with patch('tests.recovery_execution_fixtures.HMAC_KEY', b'k' * 32):
        bundle = build_bound_fixture(tmp_path)
    before = source_bytes(bundle)
    plan_path = tmp_path / 'plan.json'
    plan_path.write_bytes(json_bytes(bundle['plan']))
    key_path = tmp_path / 'existing-private-key.bin'
    fd = create_private_file(key_path)
    with os.fdopen(fd, 'wb') as stream:
        stream.write((bundle['hmac_key'].hex() + '\n').encode('ascii'))
    target = bundle['bound'].output_dir / 'reports'
    arguments = dict(plan_path=plan_path, hmac_key_path=key_path,
                     output_json=target / 'review.json', output_md=target / 'review.md')
    receipt = write_readback_reports(**arguments)
    assert receipt['execution_status'] == 'NOT_STARTED'
    assert len(receipt['outputs']) == 2
    assert not bundle['bound'].journal_path.exists()
    assert not bundle['bound'].journal_path.with_name('recovery_execution.jsonl.lock').exists()
    assert key_path.read_bytes() == (bundle['hmac_key'].hex() + '\n').encode('ascii') and source_bytes(bundle) == before
    with pytest.raises(ValueError):
        write_readback_reports(**arguments)


def test_cli_missing_key_does_not_create_it_or_execute(tmp_path):
    bundle = build_bound_fixture(tmp_path)
    plan_path = tmp_path / 'plan.json'
    plan_path.write_bytes(json_bytes(bundle['plan']))
    key = tmp_path / 'missing-key'
    target = bundle['bound'].output_dir / 'reports'
    with pytest.raises(OSError):
        write_readback_reports(plan_path=plan_path, hmac_key_path=key,
                               output_json=target / 'r.json', output_md=target / 'r.md')
    assert not key.exists() and not bundle['bound'].output_dir.exists()


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'[' * 10])
def test_strict_report_input_rejects_invalid_json(raw):
    with pytest.raises(ValueError):
        read_strict_json(raw)
