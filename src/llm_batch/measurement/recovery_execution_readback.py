"""합성 복구 원장과 출력 후보를 원본 결속으로 독립 재판독한다."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from .recovery_execution_contract import (
    BoundRecoveryPlan, canonical_sha256, execution_journal_arguments,
    read_bound_input_posts,
)
from ..ledger.recovery_execution_journal import FINALIZATION_ELAPSED_SCOPE, read_execution_journal


class RecoveryExecutionReadbackError(ValueError):
    pass


_FIXED = {
    'execution_mode': 'LOCAL_SIMULATION_ONLY', 'data_kind': 'SYNTHETIC_CONTRACT_ONLY',
    'actual_external_call_count': 0, 'public_apply': False,
    'publication_authority': False, 'central_db_write': False,
    'tokens': None, 'price': None, 'formal_kpi_status': 'NOT_ESTIMABLE',
}
_OUTPUT_KEYS = set(_FIXED) | {
    'schema_version', 'status', 'binding', 'recovery_session_id', 'recovery_attempt_id',
    'actions', 'protected_sources_start', 'protected_sources_before_output',
    'elapsed_ms_before_output_write', 'receipt_sha256',
}
_ACTION_KEYS = {'action_id', 'call_id', 'action_kind', 'query_sha256',
                'reservation_ordinal', 'response', 'response_sha256', 'response_bytes'}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryExecutionReadbackError(message)


def _canonical_bytes(value: Any) -> bytes:
    canonical_sha256(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def read_strict_json(raw: bytes, *, maximum_bytes: int = 65536) -> Any:
    _require(type(raw) is bytes and len(raw) <= maximum_bytes, 'JSON 크기 제한 초과')
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'JSON 중복 키')
            result[key] = value
        return result
    def constant(_):
        raise RecoveryExecutionReadbackError('JSON 비유한 숫자')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        canonical_sha256(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RecoveryExecutionReadbackError('UTF-8 JSON 판독 실패') from exc


def _same(actual: Any, expected: Any) -> bool:
    return _canonical_bytes(actual) == _canonical_bytes(expected)


def _output_path(bound: BoundRecoveryPlan, attempt: str) -> Path:
    name = hashlib.sha256(attempt.encode('utf-8')).hexdigest() + '.json'
    return bound.assert_output_path(bound.output_dir / 'attempts' / name)


def validate_fixture_execution_events(plan: dict, fixture: dict, events: list[dict]) -> None:
    """실패도 고정 fixture에 결속하여 영구 실패를 retry 근거로 바꾸지 못하게 한다.

    journal의 exact schema/순서/예산 검산을 통과한 events를 소비한다.
    시간·취소 파생 상태는 기록된 근거가 있어야 하며 의미 품질을 평가하지 않는다.
    """
    responses = {item['action_id']: item['responses'] for item in fixture['actions']}
    reservations, terminals, cancellations, elapsed_by_attempt = {}, {}, {}, {}
    policy = plan['policy']
    for event in events:
        attempt, elapsed = event['recovery_attempt_id'], event['elapsed_ms']
        elapsed_by_attempt[attempt] = elapsed
        payload, kind = event['payload'], event['event_type']
        if kind == 'CANCEL_REQUESTED':
            cancellations[attempt] = elapsed
        elif kind == 'ACTION_RESERVED':
            action_responses = responses[payload['action_id']]
            _require(1 <= payload['reservation_ordinal'] <= len(action_responses), '예약이 고정 fixture 범위를 벗어남')
            previous_id = payload['previous_call_id']
            if previous_id is not None:
                previous = reservations[previous_id]
                previous_response = responses[previous['payload']['action_id']][previous['payload']['reservation_ordinal'] - 1]
                _require(elapsed - terminals[previous_id]['elapsed_ms'] >= previous_response['retry_delay_ms'],
                         '고정 retry 대기시간을 지키지 않은 예약')
            reservations[payload['call_id']] = event
        elif kind == 'ACTION_TERMINAL':
            reserved = reservations[payload['call_id']]
            selection = reserved['payload']
            response = responses[selection['action_id']][selection['reservation_ordinal'] - 1]
            outcome, expected = payload['outcome'], response['outcome']
            duration = elapsed - reserved['elapsed_ms']
            cancel = cancellations.get(attempt)
            waited = duration >= response['delay_ms']
            if outcome in {'SUCCESS', 'TRANSIENT_FAILURE', 'PERMANENT_FAILURE', 'CALLBACK_ERROR'}:
                _require(outcome == expected and waited, '호출 terminal과 고정 fixture 결과 또는 시간이 다름')
            elif outcome == 'CANCEL_CONFIRMED':
                _require(expected == outcome and waited,
                         '취소 확인의 고정 fixture 또는 응답 시간 근거 없음')
                _require(cancel is None or elapsed - cancel <= policy['cancel_grace_ms'],
                         '취소 중단 확인이 grace 상한을 초과함')
            elif outcome == 'NO_RESPONSE':
                _require((expected == 'NO_RESPONSE' and waited)
                         or (expected == 'SUCCESS' and response['response'] is None and waited)
                         or (cancel is not None and (waited or elapsed - cancel > policy['cancel_grace_ms'])),
                         '미응답의 fixture 또는 취소 시간 근거 없음')
            elif outcome == 'TIMEOUT':
                _require(duration > policy['per_action_timeout_ms']
                         or sum(elapsed_by_attempt.values()) > policy['max_elapsed_ms'],
                         '시간 초과 terminal에 예산 근거 없음')
            elif outcome == 'OUTPUT_LIMIT':
                _require(expected == 'SUCCESS' and type(response['response']) is dict and waited
                         and len(_canonical_bytes(response['response'])) > policy['max_output_bytes'],
                         '응답 상한 초과의 fixture 근거 없음')
            else:
                raise RecoveryExecutionReadbackError('알 수 없는 호출 결과')
            if outcome == 'SUCCESS':
                _require(type(response['response']) is dict, '성공 fixture 응답 누락')
                raw = _canonical_bytes(response['response'])
                _require(payload['response_sha256'] == hashlib.sha256(raw).hexdigest()
                         and payload['response_bytes'] == len(raw), '성공 terminal의 fixture 응답 결속 불일치')
            else:
                _require(payload['response_sha256'] is None and payload['response_bytes'] == 0,
                         '실패 terminal이 성공 응답을 보유함')
            terminals[payload['call_id']] = event


def _verify_output(bound, plan, binding, events, terminal, protected):
    payload = terminal['payload']
    _require(payload['status'] == 'COMPLETED_SIMULATION', '출력은 완료 terminal에만 결속 가능')
    path = _output_path(bound, terminal['recovery_attempt_id'])
    _require(path.is_file(), '완료 출력 파일 누락')
    _require(path.stat().st_size <= plan['policy']['max_output_bytes'], '출력 파일 상한 초과')
    raw = path.read_bytes()
    _require(len(raw) == payload['output_bytes'] and hashlib.sha256(raw).hexdigest() == payload['output_sha256'],
             '완료 출력 원시 SHA 또는 크기 불일치')
    output = read_strict_json(raw, maximum_bytes=plan['policy']['max_output_bytes'])
    _require(type(output) is dict and set(output) == _OUTPUT_KEYS, '출력 exact schema 불일치')
    _require(raw == _canonical_bytes(output) + b'\n', '출력 저장 형식 불일치')
    _require(output['schema_version'] == 'recovery_simulation_output_v1'
             and output['status'] == 'SIMULATION_OUTPUT_CANDIDATE', '출력 schema 또는 후보 상태 불일치')
    for key, expected in _FIXED.items():
        _require(_same(output[key], expected), '출력 권한 또는 미측정 필드 불일치: ' + key)
    _require(output['receipt_sha256'] == canonical_sha256({k: v for k, v in output.items() if k != 'receipt_sha256'}),
             '출력 자체 SHA 불일치')
    _require(_same(output['binding'], binding), '출력 계획 결속 불일치')
    for key in ('recovery_attempt_id', 'recovery_session_id'):
        _require(output[key] == terminal[key], '출력 시도 또는 세션 불일치')
    _require(_same(output['protected_sources_start'], protected)
             and _same(output['protected_sources_before_output'], protected), '출력 보호 원본 지문 불일치')
    elapsed = output['elapsed_ms_before_output_write']
    _require(type(elapsed) is int and 0 <= elapsed <= terminal['elapsed_ms'], '출력 시간 순서 불일치')
    preceding = [event for event in events if event['sequence'] < terminal['sequence']]
    current = [event['elapsed_ms'] for event in preceding
               if event['recovery_attempt_id'] == terminal['recovery_attempt_id']]
    _require(not current or elapsed >= max(current), '출력 시각이 현재 시도의 앞선 사건보다 빠름')
    reservations = {event['payload']['call_id']: event for event in preceding if event['event_type'] == 'ACTION_RESERVED'}
    successes = {}
    for event in preceding:
        if event['event_type'] == 'ACTION_TERMINAL' and event['payload']['outcome'] == 'SUCCESS':
            reservation = reservations[event['payload']['call_id']]
            successes[reservation['payload']['action_id']] = (reservation, event)
    actions = output['actions']
    _require(type(actions) is list and len(actions) == len(plan['actions']), '출력 action 분모 불일치')
    fixture = {item['action_id']: item for item in bound.fixture['actions']}
    for action, declared in zip(plan['actions'], actions):
        _require(type(declared) is dict and set(declared) == _ACTION_KEYS, '출력 action exact schema 불일치')
        _require(action['action_id'] in successes, '성공 terminal이 없는 출력 action')
        reservation, completed = successes[action['action_id']]
        reserved, result = reservation['payload'], completed['payload']
        expected = {'action_id': action['action_id'], 'call_id': reserved['call_id'],
                    'action_kind': action['kind'], 'query_sha256': action['query_sha256'],
                    'reservation_ordinal': reserved['reservation_ordinal']}
        _require(all(_same(declared[key], value) for key, value in expected.items()), '출력 action 좌표 불일치')
        responses = fixture[action['action_id']]['responses']
        ordinal = reserved['reservation_ordinal']
        _require(1 <= ordinal <= len(responses), 'fixture 응답 순서 범위 이탈')
        response = responses[ordinal - 1]
        _require(response['outcome'] == 'SUCCESS' and type(response['response']) is dict
                 and _same(declared['response'], response['response']), '출력과 고정 성공 fixture 불일치')
        raw_response = _canonical_bytes(declared['response'])
        sha = hashlib.sha256(raw_response).hexdigest()
        _require(type(declared['response_bytes']) is int
                 and declared['response_bytes'] == len(raw_response) == result['response_bytes']
                 and declared['response_sha256'] == sha == result['response_sha256'], '응답과 호출 terminal 결속 불일치')
    return {'path': str(path), 'sha256': payload['output_sha256'], 'bytes': len(raw)}


def build_recovery_execution_readback(bound_plan: BoundRecoveryPlan, *, journal_path: str | Path | None = None) -> dict:
    """새 파일·lock·원장 수리 없이 고정 한 plan의 전체 입력과 시도를 읽는다."""
    _require(type(bound_plan) is BoundRecoveryPlan, '검산된 BoundRecoveryPlan 필요')
    plan = bound_plan.plan
    protected = bound_plan.verify_protected_sources()
    expected_path = bound_plan.assert_output_path(bound_plan.journal_path)
    if journal_path is not None:
        _require(Path(journal_path).absolute() == expected_path.absolute(), '고정 원장 경로와 다름')
    existed = expected_path.exists()
    _require(not existed or expected_path.is_file(), '원장은 일반 파일이어야 함')
    _require(not existed or expected_path.stat().st_size <= 8 * 1024 * 1024, '원장 크기 제한 초과')
    raw = expected_path.read_bytes() if existed else b''
    arguments = execution_journal_arguments(plan)
    state = read_execution_journal(raw, **arguments)
    events = state['events']
    validate_fixture_execution_events(plan, bound_plan.fixture, events)
    attempts = []
    observed_outputs = []
    for start in (event for event in events if event['event_type'] == 'ATTEMPT_STARTED'):
        attempt_id = start['recovery_attempt_id']
        own = [event for event in events if event['recovery_attempt_id'] == attempt_id]
        terminals = [event for event in own if event['event_type'] == 'ATTEMPT_TERMINAL']
        finals = [event for event in own if event['event_type'] == 'ATTEMPT_FINALIZED']
        _require(len(terminals) <= 1, '중복 attempt terminal')
        _require(len(finals) <= 1, '중복 attempt finalization')
        terminal = terminals[0] if terminals else None
        final = finals[0] if finals else None
        # 원장의 상태 검산은 final과 terminal의 SHA·시간·허용 상태 전이를 먼저 확인한다.
        status = final['payload']['status'] if final else 'INCOMPLETE'
        candidate_output = None
        if terminal and terminal['payload']['status'] == 'COMPLETED_SIMULATION':
            candidate_output = _verify_output(bound_plan, plan, arguments['binding'], events, terminal, protected)
            observed_outputs.append(candidate_output)
        elif terminal:
            _require(terminal['payload']['output_sha256'] is None and terminal['payload']['output_bytes'] == 0,
                     '실패 또는 미완료를 출력 성공으로 결속할 수 없음')
        output = candidate_output if status == 'COMPLETED_SIMULATION' else None
        attempts.append({'recovery_attempt_id': attempt_id, 'recovery_session_id': start['recovery_session_id'],
                         'status': status, 'terminal_recorded': terminal is not None,
                         'terminal_candidate_status': terminal['payload']['status'] if terminal else None,
                         'finalization_recorded': final is not None,
                         'reason_codes': final['payload']['reason_codes'] if final else
                             (['ATTEMPT_NOT_FINALIZED'] if terminal else ['ATTEMPT_NOT_TERMINAL']),
                         'reserved_dispatches': sum(event['event_type'] == 'ACTION_RESERVED' for event in own),
                         'last_elapsed_ms': max(event['elapsed_ms'] for event in own),
                         'candidate_output': candidate_output, 'output': output})
    latest = attempts[-1]['status'] if attempts else 'NOT_STARTED'
    posts = read_bound_input_posts(bound_plan)
    _require(len(posts) == plan['base']['input_count'], '전체 입력 분모 불일치')
    rows = []
    for index, post in enumerate(posts, 1):
        post_id = post['post_id']
        selected = index == plan['base']['input_index']
        if selected:
            _require(_same(post_id, plan['base']['post_id']), '선택 행의 post 타입 또는 값 불일치')
        rows.append({'input_index': index, 'post_id': post_id, 'plan_provided': selected,
                     'state': latest if selected else 'NO_PLAN_PROVIDED', 'attempt_count': len(attempts) if selected else 0})
    _require(sum(row['plan_provided'] for row in rows) == 1, '선택 base 분모 불일치')
    _require(canonical_sha256([row['post_id'] for row in rows]) == plan['base']['input_order_sha256'], '입력 순서 불일치')
    counters = Counter(event['payload']['outcome'] for event in events if event['event_type'] == 'ACTION_TERMINAL')
    _require(_same(bound_plan.verify_protected_sources(), protected), '판독 중 보호 원본 변경')
    _require(expected_path.exists() == existed and (not existed or expected_path.read_bytes() == raw), '판독 중 원장 변경')
    for output in observed_outputs:
        path = bound_plan.assert_output_path(output['path'])
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == output['sha256'], '판독 중 출력 변경')
    report = {
        'schema_version': 'recovery_execution_readback_v1', 'verification_status': 'VERIFIED_LOCAL_CONTRACT',
        'execution_status': latest, **_FIXED, 'plan_sha256': plan['plan_sha256'],
        'binding_sha256': plan['binding_sha256'], 'base': deepcopy(plan['base']),
        'journal': {'path': str(expected_path), 'exists': existed, 'sha256': hashlib.sha256(raw).hexdigest(),
                    'bytes': len(raw), 'head_sha256': state['head_sha256'], 'event_count': len(events)},
        'input_count': len(rows), 'selected_base_count': 1, 'attempt_count': len(attempts),
        'input_rows': rows, 'attempts': attempts,
        'consumed_simulated_dispatches': state['consumed_simulated_dispatches'],
        'consumed_action_count': state['consumed_action_count'], 'consumed_elapsed_ms': state['consumed_elapsed_ms'],
        'pending_finalization_count': len(state['pending_finalization_attempt_ids']),
        'budget_observation_scope': FINALIZATION_ELAPSED_SCOPE,
        'finalization_persistence_in_budget': False,
        'open_call_count': len(state['open_call_ids']), 'action_outcomes': dict(sorted(counters.items())),
        'protected_sources': protected,
        'limitations': ['SYNTHETIC_CONTRACT_ONLY', 'ONE_EXPLICIT_PLAN', 'NO_ACTUAL_RECOVERY_QUALITY', 'NO_ACTUAL_PRICE_MEASUREMENT'],
    }
    return {**report, 'report_sha256': canonical_sha256(report)}


def validate_recovery_execution_readback(report: Any, *, bound_plan: BoundRecoveryPlan) -> dict:
    expected = build_recovery_execution_readback(bound_plan)
    _require(type(report) is dict and _same(report, expected), '저장 판독 보고서가 현재 원본 재생과 다름')
    return deepcopy(expected)


def render_korean_report(report: dict) -> str:
    """미관측 입력과 합성 시도를 구분한 한국어 읽기용 보고서."""
    def cell(value):
        return str(value).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')
    lines = ['# 제한 복구 실행 기록 판독', '',
             f"원장·출력 검산은 `{report['verification_status']}`, 실행 상태는 `{report['execution_status']}`다.",
             '고정 fixture로 수행한 로컬 합성 기록이다. 실제 검색·모델 호출과 복구 품질·비용 평가를 의미하지 않는다.', '',
             f"전체 입력 {report['input_count']}건 중 명시 계획 1건, 복구 시도 {report['attempt_count']}개를 판독했다. "
             '다른 입력의 NO_PLAN_PROVIDED는 검토 결과나 실패 판정이 아니다.', '',
             f"합성 예약 {report['consumed_simulated_dispatches']}회, 미종결 예약 {report['open_call_count']}회, "
             f"누적 관측 시간 {report['consumed_elapsed_ms']}ms. 실제 외부 호출은 0회이며 formal KPI는 NOT_ESTIMABLE이다.", '',
             '| 입력 순서 | post ID | 계획 | 상태 | 시도 수 |', '|---:|---|---|---|---:|']
    lines.extend(f"| {row['input_index']} | {cell(row['post_id'])} | {'있음' if row['plan_provided'] else '없음'} | {row['state']} | {row['attempt_count']} |"
                 for row in report['input_rows'])
    lines += ['', '| 복구 시도 | 상태 | 예약 수 | 종결 후보 | 최종화 |', '|---|---|---:|---|---|']
    lines.extend(f"| {cell(row['recovery_attempt_id'])} | {row['status']} | {row['reserved_dispatches']} | {'있음' if row['terminal_recorded'] else '없음'} | {'있음' if row['finalization_recorded'] else '없음'} |"
                 for row in report['attempts'])
    lines += ['', f"계획 SHA: `{report['plan_sha256']}`", f"원장 SHA: `{report['journal']['sha256']}`",
              f"보고서 SHA: `{report['report_sha256']}`", '',
              '시간 예산은 종결 후보의 저장·재판독까지 관측한다. 마지막 관측 기록 자체의 저장은 보고서 I/O로 별도이며 예산에 포함하지 않는다.',
              '공개 적용·중앙 DB 쓰기는 비활성이다. 보호 원본 지문은 JSON 보고서에 기록한 명시 참조 범위에 한한다.', '']
    return '\n'.join(lines)
