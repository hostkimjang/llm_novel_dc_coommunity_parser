"""실제 파일 원장과 HTTP mock을 사용한다. 외부 모델·검색은 호출하지 않는다."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

import httpx
import pytest

from src.llm_batch.runtime import recovery_native_io as native
from src.llm_batch.runtime import recovery_transport as transport
from src.llm_batch.ledger import recovery_native_journal as native_journal
from src.llm_batch.runtime.recovery_provider_transport import RecoveryProviderRunner
from src.llm_batch.ledger.recovery_native_journal import NativeRecoveryError, canonical_bytes, canonical_sha256


class Clock:
    def __init__(self): self.value = 1000
    def __call__(self): return self.value


class Body(httpx.SyncByteStream):
    def __init__(self, raw): self.raw = raw
    def __iter__(self): yield self.raw


def response(value, *, raw=None, status=200):
    return httpx.Response(status, stream=Body(raw if raw is not None else canonical_bytes(value)))


def provider_receipt(tmp_path):
    policy = {'max_calls':1, 'max_elapsed_ms':1000, 'request_timeout_ms':500,
              'max_response_bytes':4096, 'max_total_response_bytes':4096}
    payload = {'query':'합성 upstream', 'num_results':1, 'purpose':'native_test'}
    endpoint = 'http://provider.test/mcp/search'
    binding = {k:'a'*64 for k in ('plan_sha256','base_sha256','source_sha256','config_sha256')}
    binding.update(policy_sha256=canonical_sha256(policy), publication_scope_id='test-scope',
                   input_index=1, post_id=7, base_attempt_run_id='base-test-attempt')
    requests = [{'request_id':'upstream', 'kind':'MCP_SEARCH', 'body_sha256':canonical_sha256(payload),
                 'endpoint_sha256':hashlib.sha256(endpoint.encode()).hexdigest()}]
    runner = RecoveryProviderRunner(binding=binding, policy=policy, requests=requests,
        journal_path=tmp_path/'upstream/provider.jsonl', endpoints={'MCP_SEARCH':endpoint},
        source_check=lambda:True, cancelled=lambda:False, clock_ms=Clock(),
        test_transport=httpx.MockTransport(lambda req:response({'results':[]})))
    result = runner.request('MCP_SEARCH', payload, request_id='upstream')
    assert result['status'] == 'SUCCESS'
    return result


def make_io(tmp_path, monkeypatch, *, handler=None, policy=None, clock=None, source=None):
    monkeypatch.setattr(native, 'NATIVE_JOB_REGISTRY_ROOT', tmp_path/'registry')
    upstream = provider_receipt(tmp_path)
    clock = clock or Clock()
    state = {'sent':[], 'source':True, 'cancelled':False}
    policy = policy or {'max_calls':8, 'max_elapsed_ms':10000, 'request_timeout_ms':1000,
                        'max_response_bytes':8192, 'max_total_response_bytes':65536}
    binding = {k:canonical_sha256(k) for k in ('base_sha256','source_sha256','config_sha256','context_sha256')}
    binding['upstream_sha256'] = canonical_sha256(upstream)
    def handle(request):
        current = io.journal.snapshot()
        opened = current['calls'][current['open_request_id']]['reserved']['payload']
        assert opened['body_ref']['sha256'] == hashlib.sha256(request.content).hexdigest()
        assert (io.journal.path.parent/opened['body_ref']['path']).read_bytes() == request.content
        state['sent'].append(request)
        if handler: return handler(request, state, clock)
        body = json.loads(request.content)
        if request.url.path.endswith('/chat/completions'):
            return response({'model':'synthetic-model', 'choices':[{'message':{'content':'{"ok":true}'}, 'finish_reason':'stop'}],
                             'usage':{'prompt_tokens':5,'completion_tokens':3,'total_tokens':8}})
        if request.url.path.endswith('/fetch'):
            return response({'url':body['url'], 'domain':'novelpia.com','text':'합성 작품 본문','structured_info':{}})
        value = {'results':[{'title':'합성 작품','url':'https://novelpia.com/novel/1'}]}
        if 'source_receipt' in body:
            value.update(direct_search_binding_verified=True,
                         direct_search_source_receipt_sha256=canonical_sha256(body['source_receipt']))
        return response(value)
    kwargs = dict(binding=binding, policy=policy,
        endpoints={'OPENAI_CHAT':'http://model.test/v1/chat/completions',
                   'MCP_SEARCH':'http://search.test/mcp/search','MCP_FETCH':'http://search.test/mcp/fetch'},
        journal_path=tmp_path/'native/native.jsonl', upstream_receipt=upstream,
        source_check=source or (lambda:state['source']), cancelled=lambda:state['cancelled'],
        test_transport=httpx.MockTransport(handle), clock_ms=clock)
    io = native.NativeRecoveryIO(**kwargs)
    return io, kwargs, state, clock


def search(io, request_id='one', query='합성'):
    return io.request('MCP_SEARCH', {'query':query,'num_results':1,'purpose':'test'},
                      request_id=request_id, context_sha256=io.context_sha256)


def test_actual_facade_sequence_shares_durable_budget_and_completed_job_replays(tmp_path, monkeypatch):
    io, kwargs, state, clock = make_io(tmp_path, monkeypatch)
    llm = native.NativeLLMFacade(io, 'synthetic-model', 1024)
    mcp = native.NativeMCPFacade(io)
    assert llm.complete_json('합성 전문가', {'post':'원문'}) == {'ok':True}
    found = mcp.search('합성 작품')
    assert mcp.fetch(found['results'][0]['url'])['text'] == '합성 작품 본문'
    assert llm._stream_chat_http([{'role':'user','content':'추가 증거 재검토'}], tag='final_semantic_reread') == '{"ok":true}'
    io.check()
    result = {'native_guard_status':'HOLD','public_apply':False}
    final = io.finish(result)
    assert final['status'] == 'COMPLETED_NATIVE_IO' and final['native_result'] == result
    assert final['budget']['reservations_consumed'] == final['budget']['transport_invocations'] == 4
    assert final['total_client_http_invocations'] == 5 and final['total_actual_external_calls'] == 0
    assert final['remote_dispatch_count'] is None and final['price']['amount'] is None
    assert final['native_guard_evaluated_by_io'] is False and not final['publication_authority']
    before = {str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    clock.value += 999999
    restarted = native.NativeRecoveryIO(**kwargs)
    replay = restarted.readback()
    assert replay['status'] == 'COMPLETED_NATIVE_IO' and replay['native_result'] == result
    assert replay['replayed'] and replay['transport_invocations_this_invocation'] == replay['actual_external_calls'] == 0
    assert replay['native_result_ref'] == final['native_result_ref'] and len(state['sent']) == 4
    assert {str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_source_bound_search_and_llama_settings_preserved_in_actual_wire(tmp_path, monkeypatch):
    io, _, state, _ = make_io(tmp_path, monkeypatch)
    llm = native.NativeLLMFacade(io, 'synthetic-model', 1024, server_type='llama',
        min_p=0.02, repeat_penalty=1.1, temperature_by_tag={'decoder':0.4})
    llm._stream_chat_http([{'role':'user','content':'내용'}], tag='decoder', max_tokens=512)
    body = json.loads(state['sent'][0].content)
    assert body['min_p'] == 0.02 and body['repeat_penalty'] == 1.1 and body['temperature'] == 0.4
    assert body['max_tokens'] == 512 and body['stream'] is False
    mcp = native.NativeMCPFacade(io)
    source = {'run_id':'r','post_id':7,'source_receipt':{'source_sha256':'a'*64}}
    assert mcp.search('정확 제목', purpose='official_title_verify', source_binding=source)['direct_search_binding_verified']
    assert json.loads(state['sent'][1].content)['source_receipt'] == source['source_receipt']


def test_legacy_transport_payload_contract_unchanged_and_native_fetch_opt_in():
    payload = {'query':'x','num_results':1,'purpose':''}
    assert transport._payload('MCP_SEARCH', payload) == canonical_bytes(payload)
    fetch = {'url':'https://novelpia.com/novel/1','max_length':0}
    with pytest.raises(transport.RecoveryTransportError): transport._payload('MCP_FETCH', fetch)
    assert transport._payload('MCP_FETCH', fetch, native_payload=True) == canonical_bytes(fetch)
    bound = {**payload, 'purpose':'official_title_verify','run_id':'r','post_id':7,'source_receipt':{}}
    with pytest.raises(transport.RecoveryTransportError): transport._payload('MCP_SEARCH', bound)
    assert transport._payload('MCP_SEARCH', bound, native_payload=True) == canonical_bytes(bound)


def _chat_body_with_exact_bytes(size):
    body = {'model':'synthetic-model', 'max_tokens':16, 'stream':False,
            'messages':[{'role':'user', 'content':'원문 보존'}]}
    body['messages'][0]['content'] += 'x' * (size - len(canonical_bytes(body)))
    assert len(canonical_bytes(body)) == size
    return body


@pytest.mark.parametrize('size', [65 * 1024, 1024 * 1024])
def test_native_large_body_is_preserved_through_reserve_store_and_completed_replay(tmp_path, monkeypatch, size):
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch)
    body = _chat_body_with_exact_bytes(size)
    raw = canonical_bytes(body)
    value = io.request('OPENAI_CHAT', body, request_id='native-large', context_sha256=io.context_sha256)
    assert value['status'] == 'SUCCESS' and len(state['sent']) == 1
    assert state['sent'][0].content == raw
    reserved = io.journal.snapshot()['calls']['native-large']['reserved']['payload']
    assert reserved['body_ref']['bytes'] == size
    assert reserved['body_ref']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert (io.journal.path.parent / reserved['body_ref']['path']).read_bytes() == raw
    result = {'native_guard_status':'HOLD', 'public_apply':False}
    assert io.finish(result)['status'] == 'COMPLETED_NATIVE_IO'
    replay = native.NativeRecoveryIO(**kwargs).readback()
    assert replay['status'] == 'COMPLETED_NATIVE_IO' and replay['native_result'] == result
    assert replay['transport_invocations_this_invocation'] == replay['actual_external_calls'] == 0
    assert len(state['sent']) == 1


@pytest.mark.parametrize('size', [1024 * 1024, 1024 * 1024 + 1])
def test_resealed_reserved_body_limit_is_validated_by_journal(tmp_path, monkeypatch, size):
    assert native_journal.MAX_NATIVE_REQUEST_BYTES == transport.MAX_NATIVE_REQUEST_BYTES == 1024 * 1024
    io, _, state, _ = make_io(tmp_path, monkeypatch)
    assert search(io)['status'] == 'SUCCESS'
    original = io.journal.path.read_bytes()
    events = [json.loads(line) for line in original.splitlines()][:2]
    reserved = events[1]
    assert reserved['event_type'] == 'REQUEST_RESERVED'
    reserved['payload']['body_ref']['bytes'] = size
    reserved['event_sha256'] = canonical_sha256({k:v for k,v in reserved.items() if k != 'event_sha256'})
    raw = b''.join(canonical_bytes(event) + b'\n' for event in events)
    # 원장 구조 검산의 경계다. 실제 body bytes 결속과 전송/재생은 위 IO 시험이 확인한다.
    if size == transport.MAX_NATIVE_REQUEST_BYTES:
        parsed = io.journal._parse(raw)
        assert parsed['calls']['one']['reserved']['payload']['body_ref']['bytes'] == size
    else:
        with pytest.raises(NativeRecoveryError, match='NATIVE_BODY_REF_INVALID'):
            io.journal._parse(raw)
    assert io.journal.path.read_bytes() == original and len(state['sent']) == 1


def test_native_body_above_one_mib_is_rejected_before_reservation_or_transport(tmp_path, monkeypatch):
    io, _, state, _ = make_io(tmp_path, monkeypatch)
    body = _chat_body_with_exact_bytes(1024 * 1024 + 1)
    value = io.request('OPENAI_CHAT', body, request_id='native-too-large', context_sha256=io.context_sha256)
    assert value['status'] == 'NOT_AVAILABLE' and value['reason_codes'] == ['REQUEST_BYTE_LIMIT']
    snapshot = io.journal.snapshot()
    assert snapshot['started'] is None and snapshot['calls'] == {}
    assert snapshot['budget']['reservations_consumed'] == 0
    assert value['transport_invocations_this_invocation'] == value['actual_external_calls'] == 0
    assert state['sent'] == [] and not io.journal.path.exists()
    with pytest.raises(NativeRecoveryError, match='REQUEST_BYTE_LIMIT'):
        io.check()


def test_legacy_chat_still_accepts_64kib_and_rejects_65kib_before_reservation(tmp_path, monkeypatch):
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch)
    accepted = _chat_body_with_exact_bytes(64 * 1024)
    assert transport._payload('OPENAI_CHAT', accepted) == canonical_bytes(accepted)
    legacy = transport.RecoveryTransport(io._transport._gate,
        endpoints={'OPENAI_CHAT':kwargs['endpoints']['OPENAI_CHAT']},
        test_transport=kwargs['test_transport'])
    with pytest.raises(transport.RecoveryTransportError, match='REQUEST_BYTE_LIMIT'):
        legacy.request('OPENAI_CHAT', _chat_body_with_exact_bytes(65 * 1024), request_id='legacy-too-large')
    assert io.journal.snapshot()['budget']['reservations_consumed'] == 0
    assert state['sent'] == [] and not io.journal.path.exists()


@pytest.mark.parametrize('change', ['output','config','policy','context'])
def test_global_claim_denies_budget_reset_by_new_namespace_or_settings(tmp_path, monkeypatch, change):
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch)
    assert search(io)['status'] == 'SUCCESS'
    changed = dict(kwargs, binding=deepcopy(kwargs['binding']), policy=deepcopy(kwargs['policy']))
    if change == 'output': changed['journal_path'] = tmp_path/'moved/native.jsonl'
    if change == 'config': changed['binding']['config_sha256'] = 'c'*64
    if change == 'context': changed['binding']['context_sha256'] = 'd'*64
    if change == 'policy': changed['policy']['max_calls'] += 1
    other = native.NativeRecoveryIO(**changed)
    assert search(other, 'two')['status'] != 'SUCCESS'
    assert len(state['sent']) == 1


def test_finished_request_is_not_a_finished_job_restart_never_sends(tmp_path, monkeypatch):
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch)
    assert search(io)['status'] == 'SUCCESS'
    restarted = native.NativeRecoveryIO(**kwargs)
    assert restarted.readback()['status'] == 'INCOMPLETE'
    assert search(restarted, 'two')['status'] != 'SUCCESS'
    assert len(state['sent']) == 1


@pytest.mark.parametrize('cap', ['calls','bytes'])
def test_cumulative_budget_no_refund_and_sticky_terminal_failure(tmp_path, monkeypatch, cap):
    policy = {'max_calls':1 if cap == 'calls' else 8, 'max_elapsed_ms':10000,
              'request_timeout_ms':1000, 'max_response_bytes':8192,'max_total_response_bytes':8192 if cap == 'bytes' else 65536}
    io, _, state, _ = make_io(tmp_path, monkeypatch, policy=policy)
    assert search(io)['status'] == 'SUCCESS'
    assert search(io, 'two')['status'] != 'SUCCESS'
    assert io.finish({'result':'would-be-success'})['status'] != 'COMPLETED_NATIVE_IO'
    assert len(state['sent']) == 1 and io.journal.snapshot()['budget']['reserved_response_bytes'] == 8192


def test_same_request_id_with_changed_prompt_is_never_resent(tmp_path, monkeypatch):
    io, _, state, _ = make_io(tmp_path, monkeypatch)
    assert search(io)['status'] == 'SUCCESS'
    value = search(io, query='변경된 원문')
    assert value['status'] != 'SUCCESS' and value['reason_codes'] == ['NATIVE_REQUEST_ID_REUSED']
    assert len(state['sent']) == 1


def test_reserve_prework_response_and_store_share_original_deadline(tmp_path, monkeypatch):
    clock = Clock(); source_calls = [0]
    def source():
        source_calls[0] += 1
        if source_calls[0] == 1: clock.value += 80
        return True
    def handler(request, state, clock):
        clock.value += 10
        return response({'results':[]})
    policy = {'max_calls':2,'max_elapsed_ms':1000,'request_timeout_ms':100,
              'max_response_bytes':8192,'max_total_response_bytes':16384}
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch, source=source, handler=handler, clock=clock, policy=policy)
    original = native._write_new
    def delayed(path, raw):
        original(path, raw)
        if path.parent.name == 'responses' and path.suffix == '.json': clock.value += 50
    monkeypatch.setattr(native, '_write_new', delayed)
    value = search(io)
    assert value['status'] != 'SUCCESS' and len(state['sent']) == 1
    assert value['native_counts_complete'] is False and value['total_client_http_invocations'] is None
    reservation = io.journal.snapshot()['calls']['one']['reserved']['payload']
    assert reservation['request_started_elapsed_ms'] == 0 and reservation['request_deadline_elapsed_ms'] == 100
    assert native.NativeRecoveryIO(**kwargs).readback()['status'] == 'INCOMPLETE'


@pytest.mark.parametrize('damage', ['body','response','transport','result','partial_journal','anchor'])
def test_completed_replay_rechecks_every_saved_byte(tmp_path, monkeypatch, damage):
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch)
    receipt = search(io); assert receipt['status'] == 'SUCCESS'
    final = io.finish({'hold':True}); assert final['status'] == 'COMPLETED_NATIVE_IO'
    paths = {'body':io.journal.path.parent/io.journal.snapshot()['calls']['one']['reserved']['payload']['body_ref']['path'],
             'response':io.journal.path.parent/receipt['response_ref']['path'],
             'transport':io.journal.path.parent/receipt['transport_ref']['path'],
             'result':io.journal.path.parent/final['native_result_ref']['path'],
             'partial_journal':io.journal.path,'anchor':io._anchor_path}
    path = paths[damage]; before = path.read_bytes(); path.write_bytes(before + b' ')
    assert native.NativeRecoveryIO(**kwargs).readback()['status'] != 'COMPLETED_NATIVE_IO'
    assert len(state['sent']) == 1 and path.read_bytes() == before + b' '


def test_resealed_late_success_is_rejected_by_deadline_semantics(tmp_path, monkeypatch):
    io, kwargs, _, _ = make_io(tmp_path, monkeypatch)
    assert search(io)['status'] == 'SUCCESS'
    assert io.finish({'hold':True})['status'] == 'COMPLETED_NATIVE_IO'
    events = [json.loads(line) for line in io.journal.path.read_bytes().splitlines()]
    deadline = events[1]['payload']['request_deadline_elapsed_ms']
    previous = '0'*64
    for event in events:
        if event['sequence'] >= 3: event['elapsed_ms'] = deadline
        event['prev_event_sha256'] = previous
        if event['event_type'] == 'REQUEST_FINALIZED': event['payload']['terminal_sha256'] = previous
        if event['event_type'] == 'JOB_FINALIZED': event['payload']['terminal_sha256'] = previous
        event['event_sha256'] = canonical_sha256({k:v for k,v in event.items() if k != 'event_sha256'})
        previous = event['event_sha256']
    io.journal.path.write_bytes(b''.join(canonical_bytes(e)+b'\n' for e in events))
    assert native.NativeRecoveryIO(**kwargs).readback()['status'] == 'NOT_AVAILABLE'


def test_late_worker_threads_are_serial_and_use_same_gate(tmp_path, monkeypatch):
    active = [0]; maximum = [0]; guard = threading.Lock()
    def handler(request, state, clock):
        with guard:
            active[0] += 1; maximum[0] = max(maximum[0], active[0])
        try: return response({'results':[]})
        finally:
            with guard: active[0] -= 1
    io, _, state, _ = make_io(tmp_path, monkeypatch, handler=handler)
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda i:search(io, str(i)), range(2)))
    assert all(v['status'] == 'SUCCESS' for v in values)
    assert len(state['sent']) == 2 and maximum[0] == 1
    assert io.finish({'hold':True})['budget']['reservations_consumed'] == 2


@pytest.mark.parametrize('failure', ['invalid_json','source_roundtrip','callback','cancelled'])
def test_swallowed_facade_failures_cannot_finish_as_success(tmp_path, monkeypatch, failure):
    def handler(request, state, clock):
        return response({'results':[]}) if failure == 'source_roundtrip' else response({}, raw=b'not json')
    io, _, state, _ = make_io(tmp_path, monkeypatch, handler=handler)
    if failure == 'callback':
        def broken(): raise OSError('PRIVATE_PATH_MUST_NOT_ESCAPE')
        io._source_check = broken
    if failure == 'cancelled': state['cancelled'] = True
    mcp = native.NativeMCPFacade(io)
    try:
        mcp.search('합성', purpose='official_title_verify', source_binding={'run_id':'r','post_id':7,'source_receipt':{}})
    except NativeRecoveryError:
        pass  # 기존 expert가 예외를 삼킨 상황을 재현한다.
    with pytest.raises(NativeRecoveryError): io.check()
    final = io.finish({'apparently_valid':True})
    assert final['status'] != 'COMPLETED_NATIVE_IO' and 'PRIVATE_PATH' not in json.dumps(final)
    assert len(state['sent']) == (0 if failure in {'callback','cancelled'} else 1)


def test_missing_usage_is_none_and_never_provider_zero(tmp_path, monkeypatch):
    def handler(request, state, clock):
        return response({'model':'synthetic-model','choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]})
    io, _, _, _ = make_io(tmp_path, monkeypatch, handler=handler)
    llm = native.NativeLLMFacade(io, 'synthetic-model', 1024)
    assert llm.complete_json('test', {}) == {}
    assert llm.last_usage is None and llm.last_usage_provenance == 'UNAVAILABLE'
    assert llm.last_receipt['transport_receipt']['usage']['total_tokens'] is None


def test_unknown_llm_settings_are_rejected_before_any_request(tmp_path, monkeypatch):
    io, _, state, _ = make_io(tmp_path, monkeypatch)
    for kwargs in ({'server_type':'unsupported'}, {'backend':'local'}, {'tools':[]}, {'stream':True}):
        with pytest.raises(NativeRecoveryError): native.NativeLLMFacade(io, 'synthetic-model', 1024, **kwargs)
    assert state['sent'] == [] and not io.journal.path.exists()


@pytest.mark.parametrize('settings', [
    {'server_type': 'unknown'}, {'server_type': []}, {'model': ''}, {'max_tokens': True},
    {'max_tokens': 32769}, {'temperature': float('nan')}, {'top_p': False},
    {'server_type': 'llama', 'min_p': 1.1}, {'server_type': 'llama', 'repeat_penalty': -1},
    {'enable_thinking': 1}, {'min_p': 0.01}, {'vllm_top_k': 20},
    {'server_type': 'vllm', 'vllm_top_k': True}, {'server_type': 'vllm', 'vllm_top_k': -2},
    {'server_type': 'vllm', 'vllm_presence_penalty': float('inf')},
    {'server_type': 'vllm', 'vllm_presence_penalty': 2.1},
    {'server_type': 'vllm', 'repeat_penalty': 0},
    {'temperature_by_tag': []}, {'temperature_by_tag': {'decoder': True}},
    {'temperature_by_tag': {'reason_review': 2.1}}, {'stream': True},
])
def test_wire_config_preflight_rejects_without_io_or_environment(tmp_path, monkeypatch, settings):
    def forbidden(*args, **kwargs): pytest.fail('사전 설정 검산은 I/O나 환경을 읽을 수 없다')
    monkeypatch.setattr(native, 'NativeRecoveryIO', forbidden)
    monkeypatch.setattr(native.os, 'getenv', forbidden)
    before = list(tmp_path.iterdir())
    with pytest.raises((NativeRecoveryError, transport.RecoveryTransportError)):
        native.validate_native_wire_config(**{'model': 'synthetic-model', 'max_tokens': 1024, **settings})
    assert list(tmp_path.iterdir()) == before


@pytest.mark.parametrize('thinking,top_k', [(False, 13), (True, 0), (False, -1)])
def test_vllm_wire_matches_existing_client_and_keeps_pinned_config(tmp_path, monkeypatch, thinking, top_k):
    from src.llm_batch.llm.client import LLMClient
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch)
    temperatures = {'decoder': 0.4, 'reason_review': 0.3}
    config = native.validate_native_wire_config(model='synthetic-model', max_tokens=1024,
        temperature=0.2, top_p=0.9, server_type='vllm', min_p=0.02,
        repeat_penalty=1.1, enable_thinking=thinking, temperature_by_tag=temperatures,
        vllm_top_k=top_k, vllm_presence_penalty=1.25)
    llm = native.NativeLLMFacade(io, **config)
    temperatures['decoder'] = 1.9
    config['temperature_by_tag']['decoder'] = 1.8
    exposed = llm.wire_config
    exposed['temperature_by_tag']['decoder'] = 1.7
    messages = [{'role': 'user', 'content': '합성 원문'}]
    assert llm._stream_chat_http(messages, tag='decoder', max_tokens=512) == '{"ok":true}'
    body = json.loads(state['sent'][0].content)
    expected = {'model': 'synthetic-model', 'max_tokens': 512, 'temperature': 0.4,
        'top_p': 0.9, 'min_p': 0.02, 'repeat_penalty': 1.1,
        'enable_thinking': thinking, 'chat_template_kwargs': {'enable_thinking': thinking},
        'messages': messages, 'stream': False}
    if not thinking: expected['response_format'] = {'type': 'json_object'}
    # 기존 client의 순수 adapter만 호출한다. client 생성·모델·스트리밍은 없다.
    from types import SimpleNamespace
    with monkeypatch.context() as context:
        context.setenv('LLM_VLLM_TOP_K', str(top_k))
        context.setenv('LLM_VLLM_PRESENCE_PENALTY', '1.25')
        expected = LLMClient._adapt_body_for_server(SimpleNamespace(server_type='vllm'), expected)
    assert body == expected
    assert 'repeat_penalty' not in body and 'stream_options' not in body
    assert llm.wire_config['temperature_by_tag']['decoder'] == 0.4
    llm._stream_chat_http(messages, tag='decoder', temperature=0.6)
    assert json.loads(state['sent'][1].content)['temperature'] == 0.6
    assert io.finish({'hold': True})['status'] == 'COMPLETED_NATIVE_IO'
    replay = native.NativeRecoveryIO(**kwargs).readback()
    assert replay['status'] == 'COMPLETED_NATIVE_IO' and replay['replayed']
    assert replay['transport_invocations_this_invocation'] == 0 and len(state['sent']) == 2


def test_wire_config_defaults_are_explicit_and_legacy_wire_stays_unchanged():
    common = dict(model='synthetic-model', max_tokens=1024)
    standard = native.validate_native_wire_config(**common)
    assert native._native_wire_body(standard) == {**common, 'temperature': 0, 'top_p': 1}
    vllm = native.validate_native_wire_config(**common, server_type='vllm')
    assert vllm['vllm_top_k'] == 20 and vllm['vllm_presence_penalty'] == 1.5
    assert native.validate_native_wire_config(**vllm) == vllm


def test_late_native_reason_review_uses_same_gate_and_original_prompt(tmp_path, monkeypatch):
    from src.llm_batch.llm.client import REASON_REVIEW_PROMPT
    io, _, state, _ = make_io(tmp_path, monkeypatch)
    llm = native.NativeLLMFacade(io, 'synthetic-model', 1024)
    payload = {'discussion_type':'review', 'candidates':[{'id':1,'score':0.5,'sources':[],'text':'합성 근거'}]}
    assert search(io)['status'] == 'SUCCESS'
    assert llm.review_reason_candidates(payload) == {'ok':True}
    body = json.loads(state['sent'][1].content)
    assert body['messages'][0]['content'] == REASON_REVIEW_PROMPT
    assert json.loads(body['messages'][1]['content']) == payload
    assert io.finish({'hold':True})['budget']['transport_invocations'] == 2


def test_partial_response_store_keeps_evidence_and_never_retries(tmp_path, monkeypatch):
    io, kwargs, state, _ = make_io(tmp_path, monkeypatch)
    original = native._write_new
    def broken(path, raw):
        if path.parent.name == 'responses' and path.suffix == '.bin':
            original(path, raw[:3]); raise OSError('PRIVATE_PATH')
        return original(path, raw)
    monkeypatch.setattr(native, '_write_new', broken)
    assert search(io)['status'] != 'SUCCESS'
    evidence = list((io.journal.path.parent/'responses').glob('*.bin'))
    assert len(evidence) == 1 and len(evidence[0].read_bytes()) == 3
    assert search(native.NativeRecoveryIO(**kwargs), 'two')['status'] != 'SUCCESS'
    assert len(state['sent']) == 1 and len(evidence[0].read_bytes()) == 3
