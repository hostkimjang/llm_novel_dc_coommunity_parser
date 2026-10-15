"""Native 추가 요청 원장. 합성/고정 provider 원장의 wire와 권한은 바꾸지 않는다."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re

from . import recovery_execution_journal as files
from .recovery_provider_journal import canonical_bytes, canonical_sha256

SCHEMA = 'recovery_native_journal_event_v1'
GENESIS = '0' * 64
MAX_EVENTS = 520
MAX_JOURNAL_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 64 * 1024
MAX_NATIVE_REQUEST_BYTES = 1024 * 1024
BINDING_KEYS = {'source_sha256', 'config_sha256', 'base_sha256', 'context_sha256', 'upstream_sha256'}
POLICY_KEYS = {'max_calls', 'max_elapsed_ms', 'request_timeout_ms', 'max_response_bytes', 'max_total_response_bytes'}
FLAGS = {'publication_authority': False, 'public_apply': False, 'central_db_write': False}
SHA = re.compile(r'[0-9a-f]{64}\Z')


class NativeRecoveryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise NativeRecoveryError(code)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), 'NATIVE_SCHEMA_INVALID')


def sha(value):
    require(type(value) is str and SHA.fullmatch(value) is not None, 'NATIVE_SHA_INVALID')


def integer(value, maximum=2**53-1):
    require(type(value) is int and 0 <= value <= maximum, 'NATIVE_INTEGER_INVALID')


def identifier(value):
    require(type(value) is str and 0 < len(value) <= 128 and value.strip() == value
            and all(ord(c) >= 32 for c in value), 'NATIVE_IDENTIFIER_INVALID')


def configuration(binding, policy, endpoints):
    binding, policy, endpoints = deepcopy((binding, policy, endpoints))
    keys(binding, BINDING_KEYS)
    for value in binding.values(): sha(value)
    keys(policy, POLICY_KEYS)
    for value in policy.values(): integer(value)
    require(policy['max_calls'] <= 128 and policy['max_response_bytes'] <= 16 * 1024 * 1024,
            'NATIVE_POLICY_HARD_LIMIT')
    require(all(policy[k] > 0 for k in ('max_elapsed_ms', 'request_timeout_ms', 'max_response_bytes')),
            'NATIVE_POLICY_INVALID')
    require(type(endpoints) is dict and bool(endpoints)
            and set(endpoints) <= {'OPENAI_CHAT', 'MCP_SEARCH', 'MCP_FETCH'}, 'NATIVE_ENDPOINTS_INVALID')
    for value in endpoints.values(): sha(value)
    canonical_bytes([binding, policy, endpoints])
    return binding, policy, endpoints


def reference(value):
    keys(value, {'path', 'sha256', 'bytes'})
    require(type(value['path']) is str and re.fullmatch(
        r'(?:requests|responses|results)/[0-9a-f]{64}\.(?:bin|json)', value['path']), 'NATIVE_REF_PATH_INVALID')
    sha(value['sha256']); integer(value['bytes'])


def read_native_journal(raw, *, binding, policy, endpoints, journal_path):
    binding, policy, endpoints = configuration(binding, policy, endpoints)
    require(type(raw) is bytes and len(raw) <= MAX_JOURNAL_BYTES, 'NATIVE_JOURNAL_BYTE_LIMIT')
    require(not raw or raw.endswith(b'\n'), 'NATIVE_JOURNAL_INCOMPLETE')
    config_sha = canonical_sha256({'binding': binding, 'policy': policy, 'endpoints': endpoints})
    state = {'configuration_sha256': config_sha,
             'journal_path_sha256': hashlib.sha256(os.path.normcase(os.path.abspath(journal_path)).encode()).hexdigest(),
             'head_sha256': GENESIS, 'events': [], 'started': None, 'open_request_id': None,
             'blocked_reason': None, 'terminal': None, 'finalized': None, 'last_elapsed_ms': 0,
             'calls': {}, 'budget': {'reservations_consumed': 0, 'reserved_response_bytes': 0,
              'observed_response_bytes': 0, 'transport_invocations': 0, 'actual_external_calls': 0}}
    lines = raw.splitlines()
    require(len(lines) <= MAX_EVENTS, 'NATIVE_EVENT_LIMIT')
    for line in lines:
        require(0 < len(line) <= MAX_EVENT_BYTES, 'NATIVE_EVENT_BYTE_LIMIT')
        try:
            event = json.loads(line, object_pairs_hook=files._no_duplicate_keys,
                               parse_constant=lambda _: require(False, 'NATIVE_NONFINITE_JSON'))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise NativeRecoveryError('NATIVE_EVENT_JSON_INVALID') from exc
        keys(event, {'schema_version', 'sequence', 'prev_event_sha256', 'event_sha256',
                     'configuration_sha256', 'journal_path_sha256', 'event_type', 'elapsed_ms', 'payload'})
        require(canonical_bytes(event) == line and event['schema_version'] == SCHEMA, 'NATIVE_EVENT_CANONICAL_INVALID')
        require(type(event['sequence']) is int and event['sequence'] == len(state['events']) + 1
                and event['prev_event_sha256'] == state['head_sha256'], 'NATIVE_EVENT_CHAIN_INVALID')
        require(event['event_sha256'] == canonical_sha256({k:v for k,v in event.items() if k != 'event_sha256'}),
                'NATIVE_EVENT_SHA_MISMATCH')
        require(all(event[k] == state[k] for k in ('configuration_sha256', 'journal_path_sha256')),
                'NATIVE_EVENT_BINDING_MISMATCH')
        integer(event['elapsed_ms'])
        elapsed = event['elapsed_ms']
        require(elapsed >= state['last_elapsed_ms'], 'NATIVE_CLOCK_REGRESSED')
        kind, p = event['event_type'], event['payload']
        require(type(p) is dict and state['finalized'] is None, 'NATIVE_EVENT_AFTER_FINAL')
        if kind == 'JOB_STARTED':
            keys(p, {'owner_epoch', 'transport_mode'})
            identifier(p['owner_epoch'])
            require(p['transport_mode'] in {'TEST_DOUBLE', 'HTTPX_SINGLE_REQUEST'}
                    and state['started'] is None and not state['events'], 'NATIVE_START_INVALID')
            state['started'] = event
        else:
            require(state['started'] is not None, 'NATIVE_JOB_NOT_STARTED')
            if kind == 'REQUEST_RESERVED':
                keys(p, {'identity', 'body_ref', 'context_sha256', 'reservation_id', 'ordinal',
                         'request_started_elapsed_ms', 'request_deadline_elapsed_ms', 'response_bytes_reserved'})
                require(state['blocked_reason'] is None and state['open_request_id'] is None
                        and state['terminal'] is None, 'NATIVE_RESERVATION_BLOCKED')
                i = p['identity']
                keys(i, {'job_id', 'request_id', 'kind', 'body_sha256', 'endpoint_sha256', 'policy_sha256', 'request_sha256'})
                identifier(i['request_id']); identifier(p['reservation_id']); sha(p['context_sha256'])
                require(i['job_id'] == config_sha and i['policy_sha256'] == canonical_sha256(policy)
                        and i['kind'] in endpoints and i['endpoint_sha256'] == endpoints[i['kind']], 'NATIVE_REQUEST_BINDING')
                sha(i['body_sha256'])
                require(i['request_sha256'] == canonical_sha256({k:v for k,v in i.items() if k != 'request_sha256'}), 'NATIVE_REQUEST_SHA')
                require(i['request_id'] not in state['calls'], 'NATIVE_REQUEST_ID_REUSED')
                require(p['reservation_id'] not in {c['reserved']['payload']['reservation_id'] for c in state['calls'].values()},
                        'NATIVE_RESERVATION_ID_REUSED')
                reference(p['body_ref'])
                require(p['body_ref']['sha256'] == i['body_sha256']
                        and p['body_ref']['path'] == 'requests/' + i['request_sha256'] + '.json'
                        and p['body_ref']['bytes'] <= MAX_NATIVE_REQUEST_BYTES, 'NATIVE_BODY_REF_INVALID')
                b = state['budget']
                integer(p['ordinal']); integer(p['response_bytes_reserved'])
                require(p['ordinal'] == b['reservations_consumed'] + 1 <= policy['max_calls'], 'NATIVE_CALL_BUDGET')
                require(p['response_bytes_reserved'] == policy['max_response_bytes']
                        and b['reserved_response_bytes'] + p['response_bytes_reserved'] <= policy['max_total_response_bytes'], 'NATIVE_BYTE_BUDGET')
                start, deadline = p['request_started_elapsed_ms'], p['request_deadline_elapsed_ms']
                integer(start); integer(deadline)
                require(deadline == min(policy['max_elapsed_ms'], start + policy['request_timeout_ms'])
                        and start <= elapsed < deadline, 'NATIVE_REQUEST_DEADLINE')
                b['reservations_consumed'] += 1; b['reserved_response_bytes'] += p['response_bytes_reserved']
                state['calls'][i['request_id']] = {'reserved': event, 'terminal': None, 'finalized': None}
                state['open_request_id'] = i['request_id']
            elif kind == 'REQUEST_TERMINAL':
                keys(p, {'request_id', 'status', 'response_ref', 'transport_ref', 'transport_receipt_sha256',
                         'observed_response_bytes', 'transport_invocations', 'actual_external_calls'})
                require(p['request_id'] == state['open_request_id'], 'NATIVE_REQUEST_NOT_OPEN')
                call = state['calls'][p['request_id']]
                require(call['terminal'] is None, 'NATIVE_REQUEST_ALREADY_TERMINAL')
                identifier(p['status']); reference(p['transport_ref']); sha(p['transport_receipt_sha256'])
                integer(p['observed_response_bytes']); integer(p['transport_invocations'], 1); integer(p['actual_external_calls'], 1)
                expected_actual = p['transport_invocations'] if state['started']['payload']['transport_mode'] == 'HTTPX_SINGLE_REQUEST' else 0
                require(p['actual_external_calls'] == expected_actual, 'NATIVE_ACTUAL_COUNT_MISMATCH')
                if p['response_ref'] is not None: reference(p['response_ref'])
                if p['status'] == 'SUCCESS':
                    require(elapsed < call['reserved']['payload']['request_deadline_elapsed_ms']
                            and p['transport_invocations'] == 1 and p['response_ref'] is not None
                            and p['response_ref']['bytes'] == p['observed_response_bytes'], 'NATIVE_SUCCESS_INVALID')
                for key in ('observed_response_bytes', 'transport_invocations', 'actual_external_calls'):
                    state['budget'][key] += p[key]
                call['terminal'] = event
            elif kind == 'REQUEST_FINALIZED':
                keys(p, {'request_id', 'terminal_sha256', 'status', 'reason_codes'})
                require(p['request_id'] == state['open_request_id'], 'NATIVE_REQUEST_NOT_OPEN')
                call = state['calls'][p['request_id']]
                require(call['terminal'] is not None and p['terminal_sha256'] == call['terminal']['event_sha256'], 'NATIVE_TERMINAL_BINDING')
                identifier(p['status'])
                require(type(p['reason_codes']) is list and all(type(c) is str for c in p['reason_codes']), 'NATIVE_REASONS_INVALID')
                if p['status'] == 'SUCCESS':
                    require(not p['reason_codes'] and call['terminal']['payload']['status'] == 'SUCCESS'
                            and elapsed < call['reserved']['payload']['request_deadline_elapsed_ms'], 'NATIVE_FINAL_SUCCESS_INVALID')
                else:
                    require(bool(p['reason_codes']), 'NATIVE_FAILURE_REASON_MISSING')
                    state['blocked_reason'] = p['status']
                call['finalized'] = event; state['open_request_id'] = None
            elif kind == 'JOB_BLOCKED':
                keys(p, {'reason_code'}); identifier(p['reason_code'])
                require(state['terminal'] is None, 'NATIVE_JOB_ALREADY_TERMINAL')
                state['blocked_reason'] = state['blocked_reason'] or p['reason_code']
            elif kind == 'JOB_TERMINAL':
                keys(p, {'status', 'result_ref', 'request_heads_sha256'})
                require(state['terminal'] is None and state['blocked_reason'] is None
                        and state['open_request_id'] is None and elapsed < policy['max_elapsed_ms'], 'NATIVE_JOB_FINISH_BLOCKED')
                require(p['status'] == 'COMPLETED_NATIVE_IO', 'NATIVE_JOB_STATUS')
                reference(p['result_ref'])
                require(p['result_ref']['bytes'] <= policy['max_response_bytes']
                        and p['result_ref']['path'] == 'results/' + p['result_ref']['sha256'] + '.json', 'NATIVE_RESULT_LIMIT')
                heads = [c['finalized']['event_sha256'] for c in state['calls'].values()]
                require(p['request_heads_sha256'] == canonical_sha256(heads), 'NATIVE_JOB_REQUESTS_BINDING')
                state['terminal'] = event
            elif kind == 'JOB_FINALIZED':
                keys(p, {'terminal_sha256', 'status'})
                require(state['terminal'] is not None and p['terminal_sha256'] == state['terminal']['event_sha256']
                        and p['status'] == 'COMPLETED_NATIVE_IO' and elapsed < policy['max_elapsed_ms'], 'NATIVE_JOB_FINAL_INVALID')
                state['finalized'] = event
            else:
                raise NativeRecoveryError('NATIVE_EVENT_UNKNOWN')
        state['events'].append(event); state['head_sha256'] = event['event_sha256']; state['last_elapsed_ms'] = elapsed
    return state


class _Transaction:
    def __init__(self, journal, lock): self.journal, self.lock, self.active = journal, lock, True

    def _guard(self):
        require(self.active, 'NATIVE_TRANSACTION_CLOSED')
        fd, path, expected = self.lock
        files._verify_handle(fd, path, expected=expected, label='LOCK')

    def snapshot(self):
        self._guard()
        return self.journal.snapshot()

    def append(self, *, expected_head_sha256, event):
        self._guard()
        raw, info = self.journal._raw()
        state = self.journal._parse(raw)
        require(expected_head_sha256 == state['head_sha256'], 'NATIVE_JOURNAL_HEAD_CONFLICT')
        keys(event, {'event_type', 'elapsed_ms', 'payload'})
        saved = {**deepcopy(event), 'schema_version': SCHEMA, 'sequence': len(state['events']) + 1,
                 'prev_event_sha256': state['head_sha256'], 'configuration_sha256': state['configuration_sha256'],
                 'journal_path_sha256': state['journal_path_sha256']}
        saved['event_sha256'] = canonical_sha256(saved)
        frame = canonical_bytes(saved) + b'\n'
        self.journal._parse(raw + frame)
        fd = files._open_verified(self.journal.path, os.O_WRONLY | os.O_APPEND,
                                  expected=info, label='NATIVE_JOURNAL', stable_snapshot=True)
        try:
            opened = os.fstat(fd)
            offset = 0
            while offset < len(frame):
                self._guard()
                current = files._verify_handle(fd, self.journal.path, expected=opened, label='NATIVE_JOURNAL', stable_snapshot=offset == 0)
                require(current.st_size == len(raw) + offset, 'NATIVE_JOURNAL_SIZE_CHANGED')
                n = os.write(fd, frame[offset:]); require(n > 0, 'NATIVE_JOURNAL_SHORT_WRITE'); offset += n
            os.fsync(fd)
            files._verify_handle(fd, self.journal.path, expected=opened, label='NATIVE_JOURNAL')
        finally:
            os.close(fd)
        files._fsync_directory(self.journal.path.parent)
        actual, _ = self.journal._raw()
        require(actual == raw + frame, 'NATIVE_APPEND_READBACK_MISMATCH')
        self.journal._parse(actual)
        return deepcopy(saved)


class RecoveryNativeJournal:
    def __init__(self, path, *, binding, policy, endpoints):
        self.path = Path(os.path.abspath(path))
        self.binding, self.policy, self.endpoints = configuration(binding, policy, endpoints)

    def _raw(self):
        info = files._path_info(self.path, label='NATIVE_JOURNAL', missing_ok=True)
        if info is None: return b'', None
        fd = files._open_verified(self.path, os.O_RDONLY, expected=info, label='NATIVE_JOURNAL', stable_snapshot=True)
        with os.fdopen(fd, 'rb') as stream:
            raw = stream.read(MAX_JOURNAL_BYTES + 1)
            files._verify_handle(stream.fileno(), self.path, expected=info, label='NATIVE_JOURNAL', stable_snapshot=True)
        require(len(raw) <= MAX_JOURNAL_BYTES, 'NATIVE_JOURNAL_BYTE_LIMIT')
        return raw, info

    def _parse(self, raw):
        return read_native_journal(raw, binding=self.binding, policy=self.policy,
                                   endpoints=self.endpoints, journal_path=self.path)

    def snapshot(self): return self._parse(self._raw()[0])

    @contextmanager
    def transaction(self):
        files._path_info(self.path, label='NATIVE_JOURNAL', missing_ok=True)
        with files._exclusive_lock(self.path) as lock:
            tx = _Transaction(self, lock)
            try: yield tx
            finally: tx.active = False

    def append(self, *, expected_head_sha256, event):
        with self.transaction() as tx:
            return tx.append(expected_head_sha256=expected_head_sha256, event=event)
