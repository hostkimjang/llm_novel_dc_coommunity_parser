"""Native client용 동적 영속 I/O. 미완결 재시작, 숨은 retry와 공개 권한은 없다."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid

from ..ledger import recovery_execution_journal as files
from ..ledger.recovery_native_journal import (
    RecoveryNativeJournal, NativeRecoveryError, require, sha, identifier,
    reference, canonical_bytes, canonical_sha256, FLAGS,
)
from . import recovery_transport as transport
from .recovery_provider_transport import _read, _write_new

SCHEMA = 'recovery_native_io_receipt_v1'
NATIVE_JOB_REGISTRY_ROOT = Path(__file__).resolve().parents[3] / 'out' / '.recovery_native_jobs'
MAX_TRANSPORT_BYTES = 24 * 1024 * 1024


def _code(exc):
    value = getattr(exc, 'code', None)
    return value if type(value) is str and re.fullmatch(r'[A-Z][A-Z_0-9]{0,127}', value) else 'NATIVE_LOCAL_ERROR'


def _upstream(value):
    require(type(value) is dict, 'NATIVE_UPSTREAM_TYPE')
    value = deepcopy(value)
    canonical_bytes(value)
    if value.get('schema_version') == 'recovery_provider_receipt_v1':
        require(value.get('receipt_sha256') == canonical_sha256({k:v for k,v in value.items() if k != 'receipt_sha256'})
                and value.get('status') == 'SUCCESS', 'NATIVE_UPSTREAM_INVALID')
        budget = value.get('budget')
        require(type(budget) is dict, 'NATIVE_UPSTREAM_BUDGET')
        calls, actual = budget.get('transport_invocations'), budget.get('actual_external_calls')
    elif value.get('schema_version') == 'recovery_provider_report_v1':
        from ..measurement.recovery_provider_readback import validate_provider_report
        validate_provider_report(value)
        require(value.get('execution_status') == 'PROVIDER_EVIDENCE_STORED', 'NATIVE_UPSTREAM_INVALID')
        calls, actual = value.get('client_http_invocations'), value.get('actual_external_call_count')
    else:
        raise NativeRecoveryError('NATIVE_UPSTREAM_SCHEMA')
    require(all(value.get(k) is False for k in FLAGS), 'NATIVE_UPSTREAM_AUTHORITY')
    require(type(calls) is int and calls >= 0 and type(actual) is int and 0 <= actual <= calls, 'NATIVE_UPSTREAM_COUNTS')
    require(value.get('transport_mode') in {'TEST_DOUBLE', 'HTTPX_SINGLE_REQUEST'}
            and actual == (0 if value['transport_mode'] == 'TEST_DOUBLE' else calls), 'NATIVE_UPSTREAM_MODE')
    return value, {'transport_invocations': calls, 'actual_external_calls': actual}


class NativeRecoveryIO:
    """생성자는 파일/네트워크 I/O가 없다. 완료 job만 새 프로세스에서 재생한다."""
    def __init__(self, *, binding, policy, endpoints, journal_path, upstream_receipt,
                 source_check, cancelled, headers=None, test_transport=None, clock_ms=None):
        require(callable(source_check) and callable(cancelled), 'NATIVE_CALLBACK_TYPE')
        require(clock_ms is None or callable(clock_ms), 'NATIVE_CLOCK_TYPE')
        require(type(endpoints) is dict and bool(endpoints), 'NATIVE_ENDPOINTS_INVALID')
        self._endpoints = {k: transport._endpoint(v) for k,v in endpoints.items()}
        self._upstream, self._upstream_counts = _upstream(upstream_receipt)
        self.journal = RecoveryNativeJournal(journal_path, binding=binding, policy=policy,
            endpoints={k:hashlib.sha256(v.encode()).hexdigest() for k,v in self._endpoints.items()})
        self._binding, self._policy = deepcopy((self.journal.binding, self.journal.policy))
        require(self._binding['upstream_sha256'] == canonical_sha256(self._upstream), 'NATIVE_UPSTREAM_SHA_MISMATCH')
        self._config = self.journal._parse(b'')['configuration_sha256']
        self._mode = 'TEST_DOUBLE' if test_transport is not None else 'HTTPX_SINGLE_REQUEST'
        require(self._mode == self._upstream['transport_mode'], 'NATIVE_UPSTREAM_MODE_MISMATCH')
        self._source_check, self._cancelled = source_check, cancelled
        self._clock = clock_ms or (lambda: time.monotonic() * 1000)
        self._start = self._last = None
        self._epoch = uuid.uuid4().hex
        self._sticky = None
        self._lock = threading.RLock()
        self._ordinal_lock = threading.Lock()
        self._next_id = 0
        self._identity = self._body_ref = self._raw_ref = None
        self._request_start = self._deadline = None
        self._current_context = self._binding['context_sha256']
        self._registry_key = canonical_sha256({k:self._binding[k] for k in ('base_sha256', 'upstream_sha256')})
        self._registry_path = Path(NATIVE_JOB_REGISTRY_ROOT).absolute() / (self._registry_key + '.json')
        self._anchor_path = self.journal.path.with_name(self.journal.path.name + '.anchor.json')
        self._gate = transport.RecoveryBudgetGate(transport.RecoveryTransportPolicy(**self._policy),
            job_id=self._config, reserve=self._reserve, source_check=self._source_guard,
            cancelled=self._cancel_guard, clock_ms=self._now)
        self._transport = transport.RecoveryTransport(self._gate, endpoints=self._endpoints,
            headers=headers, test_transport=test_transport, raw_response_sink=self._save_raw, native_payload=True)

    @property
    def binding(self): return deepcopy(self._binding)

    @property
    def context_sha256(self): return self._current_context

    def set_context_sha256(self, value):
        sha(value)
        with self._lock: self._current_context = value

    def next_request_id(self, prefix):
        identifier(prefix)
        with self._ordinal_lock:
            self._next_id += 1
            return f'{prefix[:96]}-{self._next_id}'

    def _now(self):
        value = self._clock()
        require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 2**53-1, 'NATIVE_CLOCK_INVALID')
        require(self._last is None or value >= self._last, 'NATIVE_CLOCK_REGRESSED')
        self._last = value
        if self._start is None: self._start = value
        return value

    def _elapsed(self): return math.ceil(self._now() - self._start)

    def _cancel_guard(self):
        value = self._cancelled()
        require(type(value) is bool, 'NATIVE_CANCEL_INVALID')
        return value

    def _source_guard(self):
        require(self._source_check() is True, 'NATIVE_SOURCE_NOT_VERIFIED')
        self._time_guard()
        return True

    def _time_guard(self):
        elapsed = self._elapsed()
        require(elapsed < self._policy['max_elapsed_ms'] and (self._deadline is None or elapsed < self._deadline),
                'NATIVE_TIME_BUDGET_EXHAUSTED')

    def _guard(self):
        require(self._sticky is None, self._sticky or 'NATIVE_BLOCKED')
        require(not self._cancel_guard(), 'NATIVE_CANCELLED_UNCONFIRMED')
        self._source_guard()
        require(not self._cancel_guard(), 'NATIVE_CANCELLED_UNCONFIRMED')
        self._time_guard()

    def _claim_value(self):
        return {'schema_version': 'recovery_native_location_v1', 'job_key': self._registry_key,
                'configuration_sha256': self._config, 'journal_path': str(self.journal.path), 'transport_mode': self._mode}

    def _check_anchor(self, state):
        require(_read(self._registry_path, 4096) == canonical_bytes(self._claim_value()), 'NATIVE_JOB_LOCATION_MISMATCH')
        expected = {**self._claim_value(), 'owner_epoch': state['started']['payload']['owner_epoch']}
        require(_read(self._anchor_path, 4096) == canonical_bytes(expected), 'NATIVE_ANCHOR_MISMATCH')
        require(state['started']['payload']['transport_mode'] == self._mode, 'NATIVE_MODE_MISMATCH')

    def _append(self, tx, state, kind, payload):
        return tx.append(expected_head_sha256=state['head_sha256'],
                         event={'event_type': kind, 'elapsed_ms': self._elapsed(), 'payload': payload})

    def _ensure_job(self):
        state = self.journal.snapshot()
        if state['started'] is None:
            self._guard()
            with files._exclusive_lock(self._registry_path):
                require(files._path_info(self._registry_path, label='NATIVE_REGISTRY', missing_ok=True) is None,
                        'NATIVE_JOB_ALREADY_CLAIMED')
                require(files._path_info(self._anchor_path, label='NATIVE_ANCHOR', missing_ok=True) is None, 'NATIVE_ORPHAN_ANCHOR')
                _write_new(self._registry_path, canonical_bytes(self._claim_value()))
                with self.journal.transaction() as tx:
                    state = tx.snapshot()
                    require(state['started'] is None, 'NATIVE_CONCURRENT_JOB_START')
                    self._guard()
                    _write_new(self._anchor_path, canonical_bytes({**self._claim_value(), 'owner_epoch': self._epoch}))
                    self._append(tx, state, 'JOB_STARTED', {'owner_epoch': self._epoch, 'transport_mode': self._mode})
                    state = tx.snapshot()
        self._check_anchor(state)
        require(state['started']['payload']['owner_epoch'] == self._epoch, 'NATIVE_RESTART_INCOMPLETE')
        require(state['finalized'] is None and state['terminal'] is None, 'NATIVE_JOB_ALREADY_FINISHED')
        require(state['blocked_reason'] is None and state['open_request_id'] is None, 'NATIVE_JOB_INCOMPLETE_OR_BLOCKED')
        self._guard()
        return state

    def _block(self, code):
        self._sticky = self._sticky or code
        try:
            with self.journal.transaction() as tx:
                state = tx.snapshot()
                if (state['started'] is not None and state['started']['payload']['owner_epoch'] == self._epoch
                        and state['terminal'] is None and state['blocked_reason'] is None):
                    self._check_anchor(state)
                    self._append(tx, state, 'JOB_BLOCKED', {'reason_code': self._sticky})
        except Exception:
            pass  # Partial writes remain evidence and block restart dispatch.

    def fail(self, code):
        identifier(code)
        with self._lock: self._block(code)
        raise NativeRecoveryError(code)

    def check(self):
        with self._lock:
            try:
                self._guard()
                state = self.journal.snapshot()
                if state['started'] is not None:
                    self._check_anchor(state)
                    require(state['started']['payload']['owner_epoch'] == self._epoch, 'NATIVE_RESTART_INCOMPLETE')
                    require(state['blocked_reason'] is None and state['open_request_id'] is None
                            and state['terminal'] is None, 'NATIVE_JOB_BLOCKED')
            except Exception as exc:
                code = _code(exc); self._block(code); raise NativeRecoveryError(code) from exc

    def _store(self, folder, name, raw):
        _write_new(self.journal.path.parent / folder / name, raw)
        return {'path': folder + '/' + name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

    def _read_ref(self, ref, maximum):
        reference(ref)
        require(ref['bytes'] <= maximum, 'NATIVE_REF_BYTE_LIMIT')
        raw = _read(self.journal.path.parent / ref['path'], maximum)
        require(len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'], 'NATIVE_REF_SHA_MISMATCH')
        return raw

    def _save_raw(self, raw):
        self._raw_ref = self._store('responses', self._identity['request_sha256'] + '.bin', raw)

    def _reserve(self, proposal):
        with self.journal.transaction() as tx:
            state = tx.snapshot()
            self._check_anchor(state); self._guard()
            require(state['started']['payload']['owner_epoch'] == self._epoch, 'NATIVE_RESTART_INCOMPLETE')
            require(all(proposal.get(k) == v for k,v in self._identity.items()), 'NATIVE_RESERVATION_IDENTITY')
            require(proposal['ordinal'] == state['budget']['reservations_consumed'] + 1, 'NATIVE_RESERVATION_ORDINAL')
            reservation = uuid.uuid4().hex
            self._append(tx, state, 'REQUEST_RESERVED', {'identity': self._identity, 'body_ref': self._body_ref,
                'context_sha256': self._request_context, 'reservation_id': reservation, 'ordinal': proposal['ordinal'],
                'request_started_elapsed_ms': self._request_start, 'request_deadline_elapsed_ms': self._deadline,
                'response_bytes_reserved': self._policy['max_response_bytes']})
            return transport.DurableReservation(reservation, self._identity['request_sha256'], proposal['ordinal'])

    def _stored_call(self, state, request_id, *, unfinished=False):
        call = state['calls'][request_id]
        require(call['terminal'] is not None and (call['finalized'] is not None or unfinished), 'NATIVE_CALL_INCOMPLETE')
        reserved, terminal = call['reserved']['payload'], call['terminal']['payload']
        identity = reserved['identity']
        body_raw = self._read_ref(reserved['body_ref'], transport.MAX_NATIVE_REQUEST_BYTES)
        body = transport._decode(body_raw)
        require(transport._payload(identity['kind'], body, native_payload=True) == body_raw, 'NATIVE_BODY_CANONICAL')
        tr_raw = self._read_ref(terminal['transport_ref'], MAX_TRANSPORT_BYTES)
        tr = transport._decode(tr_raw)
        require(canonical_bytes(tr) == tr_raw and tr.get('receipt_sha256') == terminal['transport_receipt_sha256']
                == canonical_sha256({k:v for k,v in tr.items() if k != 'receipt_sha256'}), 'NATIVE_TRANSPORT_SHA')
        require(tr.get('schema_version') == transport.SCHEMA and all(tr.get(k) == v for k,v in identity.items())
                and tr.get('transport_mode') == self._mode and tr.get('reservation_consumed') is True
                and tr.get('reservation_id') == reserved['reservation_id'], 'NATIVE_TRANSPORT_BINDING')
        require(all(tr.get(k) is False for k in FLAGS), 'NATIVE_TRANSPORT_AUTHORITY')
        require(tr.get('status') == terminal['status']
                and type(tr.get('transport_invocations')) is int and type(tr.get('observed_response_bytes')) is int
                and tr['transport_invocations'] == terminal['transport_invocations']
                and tr['observed_response_bytes'] == terminal['observed_response_bytes'], 'NATIVE_TRANSPORT_COUNTS')
        require(terminal['transport_ref']['path'] == 'responses/' + identity['request_sha256'] + '.json', 'NATIVE_TRANSPORT_PATH')
        response = None
        if terminal['response_ref'] is not None:
            ref = terminal['response_ref']
            require(ref['path'] == 'responses/' + identity['request_sha256'] + '.bin', 'NATIVE_RESPONSE_PATH')
            response = self._read_ref(ref, self._policy['max_response_bytes'])
            require(tr.get('response_complete') is True and tr.get('response_sha256') == ref['sha256']
                    and tr.get('observed_response_sha256') == (ref['sha256'] if ref['bytes'] else None)
                    and tr['observed_response_bytes'] == len(response), 'NATIVE_RAW_TRANSPORT_BINDING')
        status = call['finalized']['payload']['status'] if call['finalized'] else terminal['status']
        if status == 'SUCCESS':
            require(response is not None and canonical_bytes(transport._decode(response)) == canonical_bytes(tr.get('payload')),
                    'NATIVE_RAW_PAYLOAD_MISMATCH')
        return tr, terminal['response_ref'], status

    def _receipt(self, status, *, state=None, reasons=None, tr=None, response_ref=None,
                 request_id=None, invocations=0, replayed=False, native_result=None):
        native = deepcopy(state['budget']) if state else None
        call = state['calls'].get(request_id) if state else None
        terminal = call['terminal']['payload'] if call and call['terminal'] else None
        counts_complete = state is not None and not any(c['terminal'] is None for c in state['calls'].values())
        actual = invocations if self._mode == 'HTTPX_SINGLE_REQUEST' else 0
        value = {'schema_version': SCHEMA, 'status': status, 'reason_codes': reasons or [],
            'binding': self.binding, 'configuration_sha256': self._config,
            'journal_head_sha256': state['head_sha256'] if state else None,
            'request_id': request_id, 'reservation_id': call['reserved']['payload']['reservation_id'] if call else None,
            'request_sha256': call['reserved']['payload']['identity']['request_sha256'] if call else None,
            'response_ref': deepcopy(response_ref), 'transport_ref': deepcopy(terminal['transport_ref']) if terminal else None,
            'transport_receipt_sha256': terminal['transport_receipt_sha256'] if terminal else None,
            'transport_receipt': deepcopy(tr), 'payload': deepcopy(tr['payload']) if status == 'SUCCESS' and tr else None,
            'native_result': deepcopy(native_result),
            'native_result_ref': deepcopy(state['terminal']['payload']['result_ref']) if state and state['terminal'] else None,
            'budget': native, 'upstream_counts': deepcopy(self._upstream_counts),
            'native_counts_complete': counts_complete,
            'total_client_http_invocations': self._upstream_counts['transport_invocations'] + native['transport_invocations'] if counts_complete else None,
            'total_actual_external_calls': 0 if self._mode == 'TEST_DOUBLE' else
                self._upstream_counts['actual_external_calls'] + native['actual_external_calls'] if counts_complete else None,
            'transport_mode': self._mode, 'replayed': replayed,
            'transport_invocations_this_invocation': invocations, 'actual_external_calls': actual,
            'actual_external_call_scope': 'LOCAL_HTTP_INVOCATIONS_ONLY', 'remote_dispatch_count': None,
            'remote_dispatch_status': 'UNKNOWN', 'remote_cancel_confirmed': None,
            'provider_completion': 'UNKNOWN', 'price': {'status': 'NOT_ESTIMABLE', 'amount': None},
            'restart_policy': 'COMPLETED_JOB_REPLAY_ONLY_OTHERWISE_FAIL_CLOSED',
            'time_scope': 'THROUGH_TERMINAL_DURABLE_READBACK', 'finalization_write_in_time_scope': False,
            'native_guard_evaluated_by_io': False, **FLAGS}
        value['receipt_sha256'] = canonical_sha256(value)
        return value

    def request(self, kind, payload, *, request_id, context_sha256):
        # Serialize late expert worker threads. Waiting consumes the shared job time.
        with self._lock:
            state = tr = ref = None
            invocations = 0
            try:
                identifier(request_id); sha(context_sha256)
                self._request_start = math.floor(self._now() - self._start)
                self._deadline = min(self._policy['max_elapsed_ms'], self._request_start + self._policy['request_timeout_ms'])
                self._guard()
                require(kind in self._endpoints, 'NATIVE_ENDPOINT_MISSING')
                body = transport._payload(kind, payload, native_payload=True)
                state = self._ensure_job()
                require(request_id not in state['calls'], 'NATIVE_REQUEST_ID_REUSED')
                b = state['budget']
                require(b['reservations_consumed'] < self._policy['max_calls'], 'NATIVE_CALL_BUDGET_EXHAUSTED')
                require(b['reserved_response_bytes'] + self._policy['max_response_bytes'] <= self._policy['max_total_response_bytes'],
                        'NATIVE_OUTPUT_BUDGET_EXHAUSTED')
                identity = {'job_id': self._config, 'request_id': request_id, 'kind': kind,
                    'body_sha256': hashlib.sha256(body).hexdigest(),
                    'endpoint_sha256': hashlib.sha256(self._endpoints[kind].encode()).hexdigest(),
                    'policy_sha256': canonical_sha256(self._policy)}
                identity['request_sha256'] = canonical_sha256(identity)
                self._identity, self._request_context = identity, context_sha256
                self._body_ref = self._store('requests', identity['request_sha256'] + '.json', body)
                self._raw_ref = None
                self._guard()
                tr = self._transport.request(kind, transport._decode(body), request_id=request_id)
                invocations = tr['transport_invocations']; state = self.journal.snapshot()
                require(request_id in state['calls'], tr['status'] if tr['status'] != 'SUCCESS' else 'NATIVE_RESERVATION_MISSING')
                require(tr['reservation_id'] == state['calls'][request_id]['reserved']['payload']['reservation_id'], 'NATIVE_ACK_MISMATCH')
                tr_raw = canonical_bytes(tr)
                require(len(tr_raw) <= MAX_TRANSPORT_BYTES, 'NATIVE_TRANSPORT_BYTE_LIMIT')
                tr_ref = self._store('responses', identity['request_sha256'] + '.json', tr_raw)
                with self.journal.transaction() as tx:
                    state = tx.snapshot()
                    if tr['status'] == 'SUCCESS': self._guard()
                    terminal = self._append(tx, state, 'REQUEST_TERMINAL', {'request_id': request_id,
                        'status': tr['status'], 'response_ref': self._raw_ref, 'transport_ref': tr_ref,
                        'transport_receipt_sha256': tr['receipt_sha256'], 'observed_response_bytes': tr['observed_response_bytes'],
                        'transport_invocations': invocations, 'actual_external_calls': invocations if self._mode == 'HTTPX_SINGLE_REQUEST' else 0})
                    state = tx.snapshot()
                    tr, ref, status = self._stored_call(state, request_id, unfinished=True)
                    reasons = [] if status == 'SUCCESS' else [status]
                    if status == 'SUCCESS':
                        try: self._guard()
                        except Exception as exc: status, reasons = _code(exc), [_code(exc)]
                    self._append(tx, state, 'REQUEST_FINALIZED', {'request_id': request_id,
                        'terminal_sha256': terminal['event_sha256'], 'status': status, 'reason_codes': reasons})
                    state = tx.snapshot()
                if status != 'SUCCESS': self._sticky = status
                return self._receipt(status, state=state, reasons=reasons, tr=tr, response_ref=ref, request_id=request_id, invocations=invocations)
            except Exception as exc:
                code = _code(exc); self._block(code)
                try: state = self.journal.snapshot()
                except Exception: state = None
                return self._receipt('INCOMPLETE' if state and state['open_request_id'] else 'NOT_AVAILABLE',
                    state=state, reasons=[code], request_id=request_id if type(request_id) is str else None, invocations=invocations)
            finally:
                self._identity = self._body_ref = self._raw_ref = None
                self._request_start = self._deadline = None

    def _stored_result(self, state):
        for request_id in state['calls']:
            _, _, status = self._stored_call(state, request_id)
            require(status == 'SUCCESS', 'NATIVE_JOB_HAS_FAILED_REQUEST')
        require(state['terminal'] is not None, 'NATIVE_RESULT_MISSING')
        raw = self._read_ref(state['terminal']['payload']['result_ref'], self._policy['max_response_bytes'])
        result = transport._decode(raw)
        require(canonical_bytes(result) == raw, 'NATIVE_RESULT_CANONICAL')
        return result

    def finish(self, native_result):
        with self._lock:
            state = None
            try:
                require(type(native_result) is dict, 'NATIVE_RESULT_TYPE')
                raw = canonical_bytes(native_result)
                require(len(raw) <= self._policy['max_response_bytes'], 'NATIVE_RESULT_BYTE_LIMIT')
                state = self.journal.snapshot()
                if state['finalized'] is not None:
                    replay = self.readback()
                    require(replay['status'] == 'COMPLETED_NATIVE_IO' and canonical_bytes(replay['native_result']) == raw,
                            'NATIVE_FINISHED_RESULT_MISMATCH')
                    return replay
                state = self._ensure_job()
                for request_id in state['calls']: self._stored_call(state, request_id)
                self._guard()
                ref = self._store('results', hashlib.sha256(raw).hexdigest() + '.json', raw)
                with self.journal.transaction() as tx:
                    state = tx.snapshot(); self._guard()
                    terminal = self._append(tx, state, 'JOB_TERMINAL', {'status': 'COMPLETED_NATIVE_IO', 'result_ref': ref,
                        'request_heads_sha256': canonical_sha256([c['finalized']['event_sha256'] for c in state['calls'].values()])})
                    state = tx.snapshot()
                    result = self._stored_result(state)
                    self._guard()
                    self._append(tx, state, 'JOB_FINALIZED', {'terminal_sha256': terminal['event_sha256'], 'status': 'COMPLETED_NATIVE_IO'})
                    state = tx.snapshot()
                return self._receipt('COMPLETED_NATIVE_IO', state=state, native_result=result)
            except Exception as exc:
                code = _code(exc); self._block(code)
                try: state = self.journal.snapshot()
                except Exception: state = None
                return self._receipt('NOT_AVAILABLE', state=state, reasons=[code])

    def readback(self):
        # No transaction/clock/cancel/new file. Completed jobs remain readable after deadline.
        with self._lock:
            state = None
            try:
                state = self.journal.snapshot()
                if state['started'] is None:
                    require(not os.path.lexists(self._anchor_path) and not os.path.lexists(self._registry_path), 'NATIVE_ORPHAN_CLAIM')
                    return self._receipt('NOT_STARTED', state=state, replayed=True)
                self._check_anchor(state)
                require(self._source_check() is True, 'NATIVE_SOURCE_NOT_VERIFIED')
                require(state['finalized'] is not None, 'NATIVE_RESTART_INCOMPLETE')
                result = self._stored_result(state)
                return self._receipt('COMPLETED_NATIVE_IO', state=state, replayed=True, native_result=result)
            except Exception as exc:
                return self._receipt('INCOMPLETE' if state and state['started'] and state['finalized'] is None else 'NOT_AVAILABLE',
                                     state=state, reasons=[_code(exc)], replayed=True)


def _native_wire_body(config):
    """검산된 설정을 비스트리밍 요청의 고정 부분으로 바꾼다."""
    body = {key: config[key] for key in ('model', 'max_tokens', 'temperature', 'top_p')}
    server_type = config['server_type']
    if server_type in ('llama', 'vllm'):
        if config['min_p'] is not None:
            body['min_p'] = config['min_p']
        if config['repeat_penalty'] is not None:
            key = 'repetition_penalty' if server_type == 'vllm' else 'repeat_penalty'
            body[key] = config['repeat_penalty']
        body.update(enable_thinking=config['enable_thinking'],
                    chat_template_kwargs={'enable_thinking': config['enable_thinking']})
    if server_type == 'vllm':
        if config['vllm_top_k'] > 0:
            body['top_k'] = config['vllm_top_k']
        body['presence_penalty'] = config['vllm_presence_penalty']
    return body


def validate_native_wire_config(*, model, max_tokens, temperature=0, top_p=1,
        server_type='openai', min_p=None, repeat_penalty=None, enable_thinking=False,
        temperature_by_tag=None, vllm_top_k=None, vllm_presence_penalty=None, **unsupported):
    """파일·환경·I/O를 만들지 않는 사전검산. 반환값은 workflow/facade의 공통 입력이다."""
    require(not unsupported and server_type in ('openai', 'llama', 'vllm'), 'NATIVE_LLM_SETTINGS_UNSUPPORTED')
    require(type(model) is str and bool(model.strip()), 'NATIVE_LLM_MODEL')
    require(type(max_tokens) is int and 1 <= max_tokens <= 32768, 'NATIVE_LLM_TOKEN_LIMIT')
    require(type(enable_thinking) is bool, 'NATIVE_LLM_THINKING')
    for value, low, high in ((temperature, 0, 2), (top_p, 0, 1)):
        require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
                'NATIVE_LLM_PARAMETER')
    for value, high in ((min_p, 1), (repeat_penalty, 2)):
        require(value is None or type(value) in (int, float) and math.isfinite(value) and 0 <= value <= high,
                'NATIVE_LLM_PARAMETER')
    require(server_type != 'openai' or (min_p is None and repeat_penalty is None and not enable_thinking),
            'NATIVE_LLM_SETTINGS_UNSUPPORTED')
    if server_type == 'vllm':
        vllm_top_k = 20 if vllm_top_k is None else vllm_top_k
        vllm_presence_penalty = 1.5 if vllm_presence_penalty is None else vllm_presence_penalty
        require(type(vllm_top_k) is int and -1 <= vllm_top_k <= 2**31 - 1, 'NATIVE_LLM_VLLM_TOP_K')
        require(type(vllm_presence_penalty) in (int, float) and math.isfinite(vllm_presence_penalty)
                and -2 <= vllm_presence_penalty <= 2, 'NATIVE_LLM_VLLM_PRESENCE_PENALTY')
        require(repeat_penalty is None or repeat_penalty > 0, 'NATIVE_LLM_VLLM_REPETITION_PENALTY')
    else:
        require(vllm_top_k is None and vllm_presence_penalty is None, 'NATIVE_LLM_SETTINGS_UNSUPPORTED')
    temperatures = {} if temperature_by_tag is None else temperature_by_tag
    require(type(temperatures) is dict and len(temperatures) <= 128 and all(
        type(k) is str and 1 <= len(k) <= 128 and type(v) in (int, float)
        and math.isfinite(v) and 0 <= v <= 2 for k, v in temperatures.items()), 'NATIVE_LLM_TAG_TEMPERATURE')
    config = dict(model=model, max_tokens=max_tokens, temperature=temperature, top_p=top_p,
        server_type=server_type, min_p=min_p, repeat_penalty=repeat_penalty,
        enable_thinking=enable_thinking, temperature_by_tag=deepcopy(temperatures),
        vllm_top_k=vllm_top_k, vllm_presence_penalty=vllm_presence_penalty)
    transport._payload('OPENAI_CHAT', {**_native_wire_body(config), 'stream': False,
        'messages': [{'role': 'user', 'content': 'settings check'}]}, native_payload=True)
    return config


class NativeLLMFacade:
    """Text/non-stream OpenAI·llama·vLLM 설정을 동일 사전검산과 전송에 사용한다."""
    def __init__(self, io, model, max_tokens, temperature=0, top_p=1, *, min_p=None,
                 repeat_penalty=None, enable_thinking=False, server_type='openai',
                 temperature_by_tag=None, vllm_top_k=None, vllm_presence_penalty=None, **unsupported):
        require(isinstance(io, NativeRecoveryIO), 'NATIVE_IO_TYPE')
        config = validate_native_wire_config(model=model, max_tokens=max_tokens, temperature=temperature,
            top_p=top_p, min_p=min_p, repeat_penalty=repeat_penalty, enable_thinking=enable_thinking,
            server_type=server_type, temperature_by_tag=temperature_by_tag, vllm_top_k=vllm_top_k,
            vllm_presence_penalty=vllm_presence_penalty, **unsupported)
        self.io = io
        self._wire_config = deepcopy(config)
        self._settings = _native_wire_body(config)
        self._temperatures = deepcopy(config['temperature_by_tag'])
        self.model, self.max_tokens, self.temperature, self.top_p = model, max_tokens, temperature, top_p
        self.backend, self.server_type, self.stream, self.max_retries = 'http', server_type, False, 0
        self.enable_thinking, self.print_timings = enable_thinking, False
        self.last_usage = None; self.last_usage_provenance = None; self.last_model = None; self.last_finish_reason = None
        self.last_receipt = None
        self._lock = threading.RLock()

    @property
    def wire_config(self):
        return deepcopy(self._wire_config)

    def _resolve_expert_temperature(self, tag, temperature=None):
        return temperature if temperature is not None else self._temperatures.get(tag, self._settings['temperature'])

    def complete(self, messages, *, tag='expert', use_grammar=True, max_tokens=None, quiet=False, temperature=None):
        with self._lock:
            try:
                require(type(use_grammar) is bool and type(quiet) is bool, 'NATIVE_LLM_OPTION_TYPE')
                tokens = self._settings['max_tokens'] if max_tokens is None else max_tokens
                require(type(tokens) is int and 0 < tokens <= self._settings['max_tokens'], 'NATIVE_LLM_TOKEN_LIMIT')
                body = {**deepcopy(self._settings), 'messages': deepcopy(messages), 'stream': False,
                        'max_tokens': tokens, 'temperature': self._resolve_expert_temperature(tag, temperature)}
                if use_grammar and not self._settings.get('enable_thinking', False): body['response_format'] = {'type':'json_object'}
                receipt = self.io.request('OPENAI_CHAT', body, request_id=self.io.next_request_id('llm'), context_sha256=self.io.context_sha256)
                self.last_receipt = receipt
                require(receipt['status'] == 'SUCCESS', receipt['reason_codes'][0] if receipt['reason_codes'] else 'NATIVE_LLM_FAILED')
                data = receipt['payload']; choices = data.get('choices')
                require(type(choices) is list and len(choices) == 1 and type(choices[0]) is dict, 'NATIVE_LLM_CHOICES')
                choice = choices[0]; message = choice.get('message')
                require(type(message) is dict and type(message.get('content')) is str
                        and not message.get('tool_calls') and not message.get('function_call'), 'NATIVE_LLM_CONTENT')
                self.last_finish_reason = choice.get('finish_reason')
                require(self.last_finish_reason in {None, 'stop', 'length'}, 'NATIVE_LLM_FINISH_REASON')
                usage = receipt['transport_receipt']['usage']
                # Native experts add/format these values without nullable arithmetic.
                # Partial/missing values remain in the transport receipt; expose no fake zero.
                self.last_usage = ({k:usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
                                   if usage['status'] == 'PROVIDER_REPORTED' else None)
                self.last_usage_provenance = usage['status']; self.last_model = data.get('model')
                require(self.last_model is None or self.last_model == self._settings['model'], 'NATIVE_LLM_MODEL_MISMATCH')
                return message['content']
            except Exception as exc:
                self.io.fail(_code(exc))

    def _stream_chat_http(self, messages, tag='expert', use_grammar=True, max_tokens=None, quiet=False, temperature=None):
        return self.complete(messages, tag=tag, use_grammar=use_grammar, max_tokens=max_tokens, quiet=quiet, temperature=temperature)

    def complete_json(self, system_prompt, user_payload, *, tag='complete_json', max_tokens=None, temperature=None):
        try:
            require(type(system_prompt) is str, 'NATIVE_LLM_SYSTEM_PROMPT')
            user = user_payload if type(user_payload) is str else json.dumps(user_payload, ensure_ascii=False, allow_nan=False)
            content = self.complete([{'role':'system','content':system_prompt}, {'role':'user','content':user}],
                                    tag=tag, max_tokens=max_tokens, temperature=temperature)
            from ..llm.client import LLMClient
            value = LLMClient._parse_json_object_best_effort(content)
            require(type(value) is dict and self.last_finish_reason != 'length', 'NATIVE_LLM_JSON_INVALID_OR_TRUNCATED')
            canonical_bytes(value)
            return value
        except Exception as exc: self.io.fail(_code(exc))

    def review_reason_candidates(self, payload):
        # Reuse the native prompt, never the legacy retry/network implementation.
        from ..llm.client import REASON_REVIEW_PROMPT
        return self.complete_json(REASON_REVIEW_PROMPT, payload, tag='reason_review',
                                  max_tokens=self._settings['max_tokens'])


class NativeMCPFacade:
    def __init__(self, io, *, default_num_results=10):
        require(isinstance(io, NativeRecoveryIO), 'NATIVE_IO_TYPE')
        require(type(default_num_results) is int and 1 <= default_num_results <= 100, 'NATIVE_MCP_NUM_RESULTS')
        self.io, self.default_num_results = io, default_num_results
        self.endpoint_failover, self.search_max_retries = False, 0
        self.last_receipt = None

    def search(self, query, num_results=None, purpose='', *, source_binding=None):
        try:
            body = {'query': query, 'num_results': self.default_num_results if num_results is None else num_results, 'purpose': purpose}
            source_sha = None
            if source_binding is not None:
                require(type(source_binding) is dict and set(source_binding) == {'run_id','post_id','source_receipt'}, 'NATIVE_MCP_SOURCE_BINDING')
                body.update(deepcopy(source_binding)); source_sha = canonical_sha256(source_binding['source_receipt'])
            receipt = self.io.request('MCP_SEARCH', body, request_id=self.io.next_request_id('search'), context_sha256=self.io.context_sha256)
            self.last_receipt = receipt
            require(receipt['status'] == 'SUCCESS', receipt['reason_codes'][0] if receipt['reason_codes'] else 'NATIVE_SEARCH_FAILED')
            data = receipt['payload']
            require(type(data.get('results')) is list and all(type(row) is dict for row in data['results']), 'NATIVE_SEARCH_RESPONSE')
            if source_sha is not None:
                require(data.get('direct_search_binding_verified') is True
                        and data.get('direct_search_source_receipt_sha256') == source_sha, 'NATIVE_SEARCH_SOURCE_ROUNDTRIP')
            return data
        except Exception as exc: self.io.fail(_code(exc))

    def fetch(self, url, max_length=0):
        try:
            receipt = self.io.request('MCP_FETCH', {'url':url, 'max_length':max_length},
                request_id=self.io.next_request_id('fetch'), context_sha256=self.io.context_sha256)
            self.last_receipt = receipt
            require(receipt['status'] == 'SUCCESS', receipt['reason_codes'][0] if receipt['reason_codes'] else 'NATIVE_FETCH_FAILED')
            data = receipt['payload']
            require(type(data.get('url')) is str and data['url'] == url and type(data.get('text')) is str
                    and type(data.get('structured_info')) is dict, 'NATIVE_FETCH_RESPONSE')
            return data
        except Exception as exc: self.io.fail(_code(exc))
