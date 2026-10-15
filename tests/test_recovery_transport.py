"""합성 물리 전송 계약 시험. httpx.MockTransport만 사용하며 네트워크/모델 0."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json

import httpx
import pytest

from src.llm_batch.runtime import recovery_transport as transport


class Clock:
    def __init__(self):
        self.value = 1000

    def __call__(self):
        return self.value


class Body(httpx.SyncByteStream):
    def __init__(self, data, *, before_chunk=None, before_close=None, chunk_size=None):
        self.data = data
        self.before_chunk = before_chunk
        self.before_close = before_close
        self.chunk_size = chunk_size or max(1, len(data))
        self.closed = False

    def __iter__(self):
        for start in range(0, len(self.data), self.chunk_size):
            if self.before_chunk:
                self.before_chunk()
            yield self.data[start:start + self.chunk_size]

    def close(self):
        self.closed = True
        if self.before_close:
            self.before_close()


def response(value=None, *, raw=None, status=200, headers=None, **stream_options):
    raw = raw if raw is not None else json.dumps(value if value is not None else {
        "results": [{"title": "합성 문서"}]}, ensure_ascii=False).encode()
    return httpx.Response(status, headers=headers, stream=Body(raw, **stream_options))


def setup_case(*, handler=None, reserve=None, policy=None, source_check=None, cancelled=None,
               native_payload=False):
    clock = Clock()
    state = {"source": True, "cancelled": False, "proposals": [], "requests": [], "order": []}

    def reserve_default(proposal):
        state["order"].append("durable-reservation")
        state["proposals"].append(deepcopy(proposal))
        if reserve:
            return reserve(proposal, state, clock)
        return transport.DurableReservation("reservation-" + str(proposal["ordinal"]),
                                            proposal["request_sha256"], proposal["ordinal"])

    def handle(request):
        state["order"].append("physical-request")
        state["requests"].append(request)
        return handler(request, state, clock) if handler else response()

    policy = policy or transport.RecoveryTransportPolicy(
        max_calls=3, max_elapsed_ms=1000, request_timeout_ms=500,
        max_response_bytes=4096, max_total_response_bytes=8192)
    gate = transport.RecoveryBudgetGate(policy, job_id="synthetic-job",
        reserve=reserve_default, source_check=source_check or (lambda: state["source"]),
        cancelled=cancelled or (lambda: state["cancelled"]), clock_ms=clock)
    adapter = transport.RecoveryTransport(gate, endpoints={
        "MCP_SEARCH": "http://synthetic.invalid/mcp/search",
        "OPENAI_CHAT": "http://synthetic.invalid/v1/chat/completions"},
        test_transport=httpx.MockTransport(handle), native_payload=native_payload)
    return adapter, gate, state, clock


def search(adapter, request_id="request-1", **changes):
    payload = {"query": "합성 원문 검색", "num_results": 3, "purpose": "recovery-test"}
    payload.update(changes)
    return adapter.request("MCP_SEARCH", payload, request_id=request_id)


def chat(adapter, request_id="request-1", **changes):
    payload = {"model": "synthetic-model", "messages": [{"role": "user", "content": "합성 원문"}],
               "stream": False, "max_tokens": 32}
    payload.update(changes)
    return adapter.request("OPENAI_CHAT", payload, request_id=request_id)


def assert_sealed(receipt):
    value = dict(receipt)
    digest = value.pop("receipt_sha256")
    expected = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert digest == expected
    assert receipt["publication_authority"] is False
    assert receipt["central_db_write"] is False
    assert receipt["public_apply"] is False
    assert receipt["remote_cancel_confirmed"] is None
    assert receipt["provider_completion"] == "UNKNOWN"
    assert receipt["price"] == {"status": "NOT_ESTIMABLE", "amount": None}


def test_success_requires_durable_ack_before_exactly_one_pinned_physical_request():
    adapter, gate, state, _ = setup_case()
    receipt = search(adapter)
    assert receipt["status"] == "SUCCESS"
    assert state["order"] == ["durable-reservation", "physical-request"]
    assert len(state["requests"]) == receipt["transport_invocations"] == 1
    request = state["requests"][0]
    assert request.method == "POST" and str(request.url) == "http://synthetic.invalid/mcp/search"
    assert json.loads(request.content)["query"] == "합성 원문 검색"
    assert request.headers["accept-encoding"] == "identity"
    assert all(0 < value <= 0.5 for value in request.extensions["timeout"].values())
    assert receipt["response_complete"] and receipt["local_close_observed"]
    assert receipt["transport_mode"] == "TEST_DOUBLE"
    assert gate.summary()["reservations_consumed"] == 1
    assert receipt["response_sha256"] == receipt["observed_response_sha256"]
    assert receipt["payload"]["results"][0]["title"] == "합성 문서"
    assert_sealed(receipt)


def test_payload_uses_frozen_bytes_even_if_caller_mutates_input_after_reservation():
    payload = {"query": "원래 질문", "num_results": 2, "purpose": "synthetic"}
    original = deepcopy(payload)

    def reserve(proposal, state, clock):
        payload["query"] = "예약 중 외부 변경"
        proposal["kind"] = "corrupted-callback-copy"
        return transport.DurableReservation("r", proposal["request_sha256"], proposal["ordinal"])

    adapter, _, state, _ = setup_case(reserve=reserve)
    receipt = adapter.request("MCP_SEARCH", payload, request_id="r")
    assert json.loads(state["requests"][0].content) == original
    assert receipt["kind"] == "MCP_SEARCH" and receipt["status"] == "SUCCESS"


@pytest.mark.parametrize('penalty,top_k,presence', [(1.1, 20, 1.5), (2, 1, -2), (0.01, 2**31-1, 2)])
def test_native_vllm_wire_is_explicit_reserved_then_transmitted(penalty, top_k, presence):
    adapter, gate, state, _ = setup_case(native_payload=True, handler=lambda *_: response({
        'model': 'synthetic-model', 'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]}))
    settings = dict(repetition_penalty=penalty, top_k=top_k, presence_penalty=presence,
        min_p=0.01, enable_thinking=False, chat_template_kwargs={'enable_thinking': False})
    receipt = chat(adapter, **settings)
    assert receipt['status'] == 'SUCCESS'
    assert state['order'] == ['durable-reservation', 'physical-request']
    raw = state['requests'][0].content
    body = json.loads(raw)
    assert all(body[key] == value for key, value in settings.items())
    assert 'repeat_penalty' not in body and body['stream'] is False
    assert receipt['body_sha256'] == hashlib.sha256(raw).hexdigest()
    assert transport._payload('OPENAI_CHAT', body, native_payload=True) == raw
    assert gate.summary()['reservations_consumed'] == 1
    assert_sealed(receipt)


@pytest.mark.parametrize('key,value', [
    ('repetition_penalty', 0), ('repetition_penalty', -0.1), ('repetition_penalty', 2.01),
    ('repetition_penalty', True), ('repetition_penalty', '1.1'), ('repetition_penalty', float('nan')),
    ('top_k', 0), ('top_k', -1), ('top_k', 2**31), ('top_k', True), ('top_k', 1.0),
    ('presence_penalty', -2.01), ('presence_penalty', 2.01), ('presence_penalty', True),
    ('presence_penalty', None), ('presence_penalty', float('inf')),
])
def test_native_vllm_invalid_parameters_cannot_reserve_or_send(key, value):
    adapter, gate, state, _ = setup_case(native_payload=True)
    with pytest.raises(transport.RecoveryTransportError):
        chat(adapter, **{key: value})
    assert state['proposals'] == state['requests'] == []
    assert gate.summary()['reservations_consumed'] == 0


def test_native_vllm_repetition_alias_conflict_is_rejected_even_if_values_match():
    adapter, gate, state, _ = setup_case(native_payload=True)
    with pytest.raises(transport.RecoveryTransportError, match='CHAT_NATIVE_REPETITION_CONFLICT'):
        chat(adapter, repeat_penalty=1.1, repetition_penalty=1.1)
    assert state['proposals'] == state['requests'] == []
    assert gate.summary()['reservations_consumed'] == 0


@pytest.mark.parametrize('key,value', [
    ('repetition_penalty', 1.1), ('top_k', 20), ('presence_penalty', 1.5),
    ('min_p', 0.01), ('repeat_penalty', 1.1), ('enable_thinking', False),
    ('chat_template_kwargs', {'enable_thinking': False}),
])
def test_standard_transport_still_rejects_all_native_only_chat_keys(key, value):
    adapter, gate, state, _ = setup_case()
    with pytest.raises(transport.RecoveryTransportError, match='CHAT_PAYLOAD_KEYS'):
        chat(adapter, **{key: value})
    assert state['proposals'] == state['requests'] == []
    assert gate.summary()['reservations_consumed'] == 0


@pytest.mark.parametrize("field,value", [
    ("max_calls", True), ("max_calls", -1), ("max_elapsed_ms", 0),
    ("request_timeout_ms", 1.0), ("max_response_bytes", 0),
    ("max_response_bytes", transport.MAX_RESPONSE_BYTES + 1),
    ("max_total_response_bytes", None), ("max_total_response_bytes", -1),
])
def test_policy_rejects_ambiguous_or_missing_budget(field, value):
    values = dict(max_calls=2, max_elapsed_ms=1000, request_timeout_ms=100,
                  max_response_bytes=1000, max_total_response_bytes=2000)
    values[field] = value
    with pytest.raises(transport.RecoveryTransportError):
        transport.RecoveryTransportPolicy(**values)


def test_policy_is_frozen_and_gate_identity_has_no_reset_setter():
    _, gate, _, _ = setup_case()
    with pytest.raises(FrozenInstanceError):
        gate.policy.max_calls = 99
    with pytest.raises(AttributeError):
        gate.policy = replace(gate.policy, max_calls=99)
    with pytest.raises(AttributeError):
        gate.job_id = "reset"


@pytest.mark.parametrize("zero_field,reason", [
    ("max_calls", "CALL_BUDGET_EXHAUSTED"),
    ("max_total_response_bytes", "OUTPUT_BUDGET_EXHAUSTED"),
])
def test_zero_budget_has_no_reservation_transport_or_client_construction(monkeypatch, zero_field, reason):
    policy = transport.RecoveryTransportPolicy(2, 1000, 500, 4096, 8192)
    adapter, gate, state, _ = setup_case(policy=replace(policy, **{zero_field: 0}))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: pytest.fail("client must not exist"))
    receipt = search(adapter)
    assert receipt["status"] == reason and receipt["delivery_state"] == "NOT_SENT"
    assert state["proposals"] == state["requests"] == []
    assert gate.summary()["reservations_consumed"] == 0
    assert_sealed(receipt)


@pytest.mark.parametrize("mode,expected", [
    ("raise", "RESERVATION_CALLBACK_ERROR"), ("none", "RESERVATION_ACK_INVALID"),
    ("digest", "RESERVATION_ACK_INVALID"), ("ordinal", "RESERVATION_ACK_INVALID"),
    ("bool-ordinal", "RESERVATION_ACK_INVALID"), ("empty-id", "RESERVATION_ACK_INVALID"),
])
def test_failed_or_mismatched_durable_reservation_consumes_slot_but_sends_nothing(mode, expected):
    def reserve(proposal, state, clock):
        if mode == "raise":
            raise OSError("synthetic fsync failure")
        if mode == "none":
            return None
        return transport.DurableReservation("" if mode == "empty-id" else "r",
            "0" * 64 if mode == "digest" else proposal["request_sha256"],
            True if mode == "bool-ordinal" else 99 if mode == "ordinal" else proposal["ordinal"])

    adapter, gate, state, _ = setup_case(reserve=reserve)
    receipt = search(adapter)
    assert receipt["status"] == expected and not state["requests"]
    assert receipt["reservation_consumed"] and receipt["reservation_id"] is None
    assert gate.summary()["reservations_consumed"] == 1
    assert search(adapter, request_id="new-attempt")["status"] == "GATE_BLOCKED"
    assert len(state["proposals"]) == 1


@pytest.mark.parametrize("drift,expected", [
    ("cancel", "CANCELLED_UNCONFIRMED"), ("source", "SOURCE_NOT_VERIFIED"),
    ("clock", "TIME_BUDGET_EXHAUSTED"),
])
def test_post_reservation_checks_catch_cancel_source_drift_and_spent_deadline(drift, expected):
    def reserve(proposal, state, clock):
        if drift == "cancel":
            state["cancelled"] = True
        elif drift == "source":
            state["source"] = False
        else:
            clock.value += 500
        return transport.DurableReservation("r", proposal["request_sha256"], proposal["ordinal"])

    adapter, gate, state, _ = setup_case(reserve=reserve)
    receipt = search(adapter)
    assert receipt["status"] == expected
    assert receipt["reservation_consumed"] and receipt["transport_invocations"] == 0
    assert receipt["delivery_state"] == "NOT_SENT" and not state["requests"]
    assert gate.summary()["reservations_consumed"] == 1


def test_fresh_pre_send_guard_checks_time_after_client_setup(monkeypatch):
    adapter, _, state, clock = setup_case()
    original = httpx.Client

    def delayed_client(**kwargs):
        clock.value += 500
        return original(**kwargs)

    monkeypatch.setattr(httpx, "Client", delayed_client)
    receipt = search(adapter)
    assert receipt["status"] == "TIME_BUDGET_EXHAUSTED"
    assert receipt["reservation_consumed"] and not state["requests"]


@pytest.mark.parametrize("exception,expected", [
    (httpx.ReadTimeout, "TIMEOUT_UNCONFIRMED"),
    (httpx.ConnectTimeout, "TIMEOUT_UNCONFIRMED"),
    (httpx.ConnectError, "TRANSPORT_ERROR_UNCONFIRMED"),
    (httpx.RemoteProtocolError, "TRANSPORT_ERROR_UNCONFIRMED"),
])
def test_timeout_or_connection_failure_is_one_attempt_and_remote_completion_unknown(exception, expected):
    def handler(request, state, clock):
        raise exception("synthetic only", request=request)

    adapter, gate, state, _ = setup_case(handler=handler)
    receipt = search(adapter)
    assert receipt["status"] == expected
    assert receipt["transport_invocations"] == 1 and len(state["requests"]) == 1
    assert receipt["delivery_state"] == "POSSIBLY_SENT"
    assert receipt["response_sha256"] is None and receipt["payload"] is None
    assert receipt["usage"]["total_tokens"] is None
    assert gate.summary()["blocked_reason"] == expected
    assert search(adapter, request_id="different-attempt")["status"] == "GATE_BLOCKED"
    assert len(state["requests"]) == 1
    assert_sealed(receipt)


@pytest.mark.parametrize("http_status", [301, 302, 307, 308, 401, 429, 500, 503])
def test_redirect_errors_and_rate_limits_never_redirect_failover_or_retry(http_status):
    adapter, _, state, _ = setup_case(handler=lambda *_: response(
        {"error": "synthetic"}, status=http_status,
        headers={"location": "http://unrelated.invalid/forbidden"}))
    receipt = search(adapter)
    assert receipt["status"] == "HTTP_ERROR" and receipt["http_status"] == http_status
    assert receipt["response_complete"] and receipt["payload"] is None
    assert receipt["observed_response_bytes"] > 0
    assert len(state["requests"]) == 1


@pytest.mark.parametrize("declared", [False, True])
def test_oversized_response_is_not_truncated_into_success_and_read_body_is_bounded(declared):
    policy = transport.RecoveryTransportPolicy(3, 1000, 500, 10, 20)
    body = Body(b"x" * 1000)
    adapter, gate, state, _ = setup_case(policy=policy, handler=lambda *_: httpx.Response(
        200, stream=body, headers={"content-length": "1000"} if declared else {}))
    receipt = search(adapter)
    assert receipt["status"] == "RESPONSE_BYTE_LIMIT" and receipt["payload"] is None
    assert receipt["response_sha256"] is None and not receipt["response_complete"]
    assert receipt["observed_response_bytes"] == (0 if declared else 11)
    assert gate.summary()["observed_response_bytes"] == receipt["observed_response_bytes"]
    assert body.closed and len(state["requests"]) == 1


def test_total_call_and_output_budgets_are_shared_across_distinct_request_attempt_ids():
    raw = b'{"ok":true}'
    policy = transport.RecoveryTransportPolicy(9, 1000, 500, 100, 2 * len(raw))
    adapter, gate, state, _ = setup_case(policy=policy, handler=lambda *_: response(raw=raw))
    assert search(adapter, "attempt-A")["status"] == "SUCCESS"
    assert search(adapter, "attempt-B")["status"] == "SUCCESS"
    receipt = search(adapter, "attempt-C")
    assert receipt["status"] == "OUTPUT_BUDGET_EXHAUSTED"
    assert gate.summary()["reservations_consumed"] == 2
    assert gate.summary()["observed_response_bytes"] == 2 * len(raw)
    assert len(state["requests"]) == 2

    adapter, gate, state, _ = setup_case(policy=replace(policy, max_calls=1, max_total_response_bytes=100))
    assert search(adapter, "attempt-A")["status"] == "SUCCESS"
    assert search(adapter, "attempt-B")["status"] == "CALL_BUDGET_EXHAUSTED"
    assert len(state["requests"]) == gate.summary()["reservations_consumed"] == 1


def test_total_time_does_not_reset_for_another_attempt_and_timeouts_use_remaining_budget():
    def handler(request, state, clock):
        clock.value += 300
        return response(raw=b"{}")

    policy = transport.RecoveryTransportPolicy(3, 500, 400, 4096, 8192)
    adapter, _, state, _ = setup_case(policy=policy, handler=handler)
    assert search(adapter, "attempt-A")["status"] == "SUCCESS"
    receipt = search(adapter, "attempt-B")
    assert receipt["status"] == "TIME_BUDGET_EXHAUSTED" and receipt["payload"] is None
    assert state["requests"][1].extensions["timeout"]["read"] == pytest.approx(0.2)
    assert receipt["elapsed_ms"] == 600


@pytest.mark.parametrize("stage", ["header", "body", "close"])
def test_late_response_is_never_success_even_if_http_status_is_200(stage):
    def handler(request, state, clock):
        def expire():
            clock.value += 500
        if stage == "header":
            expire()
        return response(raw=b"{}", before_chunk=expire if stage == "body" else None,
                        before_close=expire if stage == "close" else None)

    adapter, _, state, _ = setup_case(handler=handler)
    receipt = search(adapter)
    assert receipt["status"] == "TIME_BUDGET_EXHAUSTED" and receipt["payload"] is None
    assert receipt["http_status"] == 200 and len(state["requests"]) == 1
    assert receipt["elapsed_ms"] >= 500
    assert_sealed(receipt)


@pytest.mark.parametrize("stage", ["before", "header", "body", "close"])
def test_cancellation_is_not_remote_cancellation_acknowledgement(stage):
    def handler(request, state, clock):
        def cancel():
            state["cancelled"] = True
        if stage == "header":
            cancel()
        return response(raw=b"{}", before_chunk=cancel if stage == "body" else None,
                        before_close=cancel if stage == "close" else None)

    adapter, _, state, _ = setup_case(handler=handler)
    if stage == "before":
        state["cancelled"] = True
    receipt = search(adapter)
    assert receipt["status"] == "CANCELLED_UNCONFIRMED" and receipt["payload"] is None
    assert receipt["transport_invocations"] == (0 if stage == "before" else 1)
    assert receipt["remote_cancel_confirmed"] is None
    assert receipt["provider_completion"] == "UNKNOWN"


def test_source_check_exception_is_not_swallowed_into_empty_success():
    def broken():
        raise OSError("synthetic source readback error")
    adapter, gate, state, _ = setup_case(source_check=broken)
    receipt = search(adapter)
    assert receipt["status"] == "SOURCE_OR_CANCELLATION_ERROR"
    assert not state["proposals"] and not state["requests"]
    assert gate.summary()["blocked_reason"] == receipt["status"]


@pytest.mark.parametrize("invalid", [None, 0, "false"])
def test_cancellation_requires_an_observed_boolean(invalid):
    adapter, _, state, _ = setup_case(cancelled=lambda: invalid)
    assert search(adapter)["status"] == "CANCELLATION_OBSERVATION_ERROR"
    assert not state["requests"]


def test_request_id_and_durable_reservation_id_cannot_be_reused():
    def reserve(proposal, state, clock):
        return transport.DurableReservation("same-id", proposal["request_sha256"], proposal["ordinal"])
    adapter, gate, state, _ = setup_case(reserve=reserve)
    assert search(adapter, "first")["status"] == "SUCCESS"
    with pytest.raises(transport.RecoveryTransportError, match="REQUEST_ID_REUSED"):
        search(adapter, "first")
    assert search(adapter, "second")["status"] == "RESERVATION_ACK_INVALID"
    assert len(state["requests"]) == 1 and gate.summary()["reservations_consumed"] == 2


def test_concurrent_or_reentrant_request_cannot_enter_during_durable_reservation():
    nested_errors = []

    def reserve(proposal, state, clock):
        try:
            search(adapter, "nested")
        except transport.RecoveryTransportError as exc:
            nested_errors.append(exc.code)
        return transport.DurableReservation("r", proposal["request_sha256"], proposal["ordinal"])

    adapter, gate, state, _ = setup_case(reserve=reserve)
    assert search(adapter)["status"] == "SUCCESS"
    assert nested_errors == ["CONCURRENT_REQUEST_NOT_SUPPORTED"]
    assert len(state["requests"]) == gate.summary()["reservations_consumed"] == 1


@pytest.mark.parametrize("usage,expected,counts", [
    (None, "UNAVAILABLE", (None, None, None)),
    ({}, "UNAVAILABLE", (None, None, None)),
    ({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "PROVIDER_REPORTED", (0, 0, 0)),
    ({"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}, "PROVIDER_REPORTED", (2, 3, 5)),
    ({"prompt_tokens": 2, "total_tokens": None}, "PARTIAL", (2, None, None)),
    ({"total_tokens": True}, "INVALID_PROVIDER_USAGE", (None, None, None)),
    ({"total_tokens": -1}, "INVALID_PROVIDER_USAGE", (None, None, None)),
    ({"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 0}, "INCONSISTENT_PROVIDER_USAGE", (2, 3, 0)),
])
def test_chat_non_streaming_usage_unknown_zero_and_inconsistent_are_distinct(usage, expected, counts):
    adapter, _, state, _ = setup_case(handler=lambda *_: response({"choices": [], "usage": usage}))
    receipt = chat(adapter)
    assert receipt["status"] == "SUCCESS" and len(state["requests"]) == 1
    assert json.loads(state["requests"][0].content)["stream"] is False
    observed = receipt["usage"]
    assert observed["status"] == expected
    assert tuple(observed[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")) == counts
    assert_sealed(receipt)


@pytest.mark.parametrize("changes", [
    {"stream": True}, {"stream": "false"}, {"max_tokens": None}, {"max_tokens": True},
    {"max_completion_tokens": 4}, {"tools": []}, {"model": ""},
    {"messages": [{"role": "user", "content": [{"image_url": "https://synthetic.invalid/x"}]}]},
])
def test_chat_rejects_streaming_missing_limits_and_uncontrolled_multimodal_or_tools(changes):
    adapter, _, state, _ = setup_case()
    with pytest.raises(transport.RecoveryTransportError):
        chat(adapter, **changes)
    assert not state["proposals"] and not state["requests"]


@pytest.mark.parametrize("url", ["file:///tmp/x", "http://user:secret@synthetic.invalid/x",
    "http://synthetic.invalid/x?api_key=secret", "http://synthetic.invalid/x#fragment", " "])
def test_endpoint_cannot_be_non_http_or_embed_unpinned_query_credentials(url):
    _, gate, _, _ = setup_case()
    with pytest.raises(transport.RecoveryTransportError):
        transport.RecoveryTransport(gate, endpoints={"MCP_SEARCH": url})


@pytest.mark.parametrize("raw", [b"[]", b'{"x":1,"x":2}', b'{"x":NaN}', b"invalid", b"\xff"])
def test_invalid_json_never_becomes_success_and_retains_raw_response_hash(raw):
    adapter, _, state, _ = setup_case(handler=lambda *_: response(raw=raw))
    receipt = search(adapter)
    assert receipt["status"] == "INVALID_JSON_RESPONSE" and receipt["payload"] is None
    assert receipt["response_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["response_complete"] and len(state["requests"]) == 1


@pytest.mark.parametrize("headers,reason", [
    ({"content-encoding": "gzip"}, "UNSUPPORTED_CONTENT_ENCODING"),
    ({"content-length": "-1"}, "INVALID_CONTENT_LENGTH"),
    ({"content-length": "word"}, "INVALID_CONTENT_LENGTH"),
    ({"content-length": "1"}, "CONTENT_LENGTH_MISMATCH"),
])
def test_encoding_and_content_length_are_not_used_to_bypass_byte_bounds(headers, reason):
    adapter, _, _, _ = setup_case(handler=lambda *_: response(raw=b"{}", headers=headers))
    receipt = search(adapter)
    assert receipt["status"] == reason and receipt["payload"] is None


def test_close_failure_and_regressed_clock_do_not_invent_success_or_timeout():
    def broken_close():
        raise OSError("synthetic close failure")
    adapter, _, _, _ = setup_case(handler=lambda *_: response(raw=b"{}", before_close=broken_close))
    receipt = search(adapter)
    assert receipt["status"] == "LOCAL_TRANSPORT_ERROR" and receipt["payload"] is None
    assert not receipt["local_close_observed"]

    def rewind(request, state, clock):
        clock.value -= 1
        return response(raw=b"{}")
    adapter, _, _, _ = setup_case(handler=rewind)
    receipt = search(adapter)
    assert receipt["status"] == "CLOCK_INVALID_OR_REGRESSED"
    assert receipt["elapsed_ms"] is None and receipt["request_elapsed_ms"] is None


def test_authentication_never_leaks_into_receipt_or_reservation_and_headers_cannot_override_host():
    adapter, gate, state, _ = setup_case()
    adapter = transport.RecoveryTransport(gate,
        endpoints={"MCP_SEARCH": "http://synthetic.invalid/mcp/search"},
        headers={"Authorization": "Bearer synthetic-secret"}, test_transport=adapter._test_transport)
    receipt = search(adapter)
    assert state["requests"][0].headers["authorization"] == "Bearer synthetic-secret"
    assert "synthetic-secret" not in json.dumps([receipt, state["proposals"]])
    with pytest.raises(transport.RecoveryTransportError, match="AUTH_HEADERS_ONLY"):
        transport.RecoveryTransport(gate, endpoints={"MCP_SEARCH": "http://synthetic.invalid/mcp/search"},
                                    headers={"Host": "unrelated.invalid"})


def test_production_constructor_explicitly_disables_transport_retry_proxy_and_redirect(monkeypatch):
    adapter, gate, state, _ = setup_case()
    mock_transport = adapter._test_transport
    construction = {}
    original_client = httpx.Client

    def transport_factory(**kwargs):
        construction["transport"] = kwargs
        return mock_transport  # All actual I/O remains MockTransport.

    def client_factory(**kwargs):
        construction["client"] = dict(kwargs)
        return original_client(**kwargs)

    monkeypatch.setattr(httpx, "HTTPTransport", transport_factory)
    monkeypatch.setattr(httpx, "Client", client_factory)
    production = transport.RecoveryTransport(gate,
        endpoints={"MCP_SEARCH": "http://synthetic.invalid/mcp/search"})
    assert search(production)["status"] == "SUCCESS"
    assert construction["transport"] == {"retries": 0, "trust_env": False}
    assert construction["client"]["follow_redirects"] is False
    assert construction["client"]["trust_env"] is False
    assert len(state["requests"]) == 1
