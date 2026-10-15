"""R6 단일 HTTP 전송 경계. 전체 복구 실행기나 재시작 가능한 원장이 아니다.

reserve callback은 durable 저장 후에만 반환해야 한다. 이 모듈은 그 저장의
진실을 독립 검증하지 않는다. 동일 job의 모든 attempt는 같은 gate를 사용한다.
동기 HTTPX phase를 강제 중단하지 않으므로 총 deadline은 admission/사후 관측
경계다. timeout·로컬 close·취소 관측은 원격 provider 중단 확인이 아니다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import threading
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping

import httpx


SCHEMA = "recovery_transport_receipt_v1"
MAX_REQUEST_BYTES = 64 * 1024
MAX_NATIVE_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
KINDS = frozenset({"MCP_SEARCH", "OPENAI_CHAT"})
NATIVE_KINDS = KINDS | {"MCP_FETCH"}
DEADLINE_ENFORCEMENT = "ADMISSION_AND_OBSERVATION_WITH_PHASE_TIMEOUTS"


class RecoveryTransportError(ValueError):
    """입력/소유권 계약 위반. HTTP 전송을 시작하지 않는다."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _Stop(Exception):
    def __init__(self, code: str):
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RecoveryTransportError(code)


def _json_value(value: Any, depth: int = 0) -> None:
    _require(depth <= 20, "JSON_DEPTH_LIMIT")
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float:
        _require(math.isfinite(value), "NONFINITE_JSON")
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    _require(type(value) is dict, "JSON_OBJECT_TYPE")
    for key, item in value.items():
        _require(type(key) is str, "JSON_KEY_TYPE")
        _json_value(item, depth + 1)


def _canonical(value: Any) -> bytes:
    _json_value(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, OverflowError) as exc:
        raise RecoveryTransportError("JSON_ENCODING") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identifier(value: Any) -> bool:
    return (type(value) is str and 0 < len(value) <= 128
            and value.strip() == value and all(ord(c) >= 32 for c in value))


@dataclass(frozen=True)
class RecoveryTransportPolicy:
    max_calls: int
    max_elapsed_ms: int
    request_timeout_ms: int
    max_response_bytes: int
    max_total_response_bytes: int

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            minimum = 0 if name in ("max_calls", "max_total_response_bytes") else 1
            _require(type(value) is int and minimum <= value <= 2**53 - 1,
                     "INVALID_POLICY_" + name.upper())
        _require(self.max_response_bytes <= MAX_RESPONSE_BYTES, "RESPONSE_HARD_LIMIT")

    @property
    def sha256(self) -> str:
        return _sha(_canonical(asdict(self)))


@dataclass(frozen=True)
class DurableReservation:
    """예약 callback의 검산 완료 회신. 실제 durable 저장 책임은 callback 소유자다."""

    reservation_id: str
    request_sha256: str
    ordinal: int


class RecoveryBudgetGate:
    """job 단위 직렬 누적 gate. 실패 슬롯/bytes는 환불하지 않는다.

    reserve(proposal)->DurableReservation, source_check()->True,
    cancelled()->bool. callback 예외는 완료나 빈 응답으로 바뀌지 않는다.
    process 재시작에 필요한 원장 복원/동일 job 재생 방지는 후속 계약의 책임이다.
    """

    def __init__(self, policy: RecoveryTransportPolicy, *, job_id: str,
                 reserve: Callable[[dict], DurableReservation],
                 source_check: Callable[[], bool], cancelled: Callable[[], bool],
                 clock_ms: Callable[[], float] | None = None):
        _require(type(policy) is RecoveryTransportPolicy, "POLICY_TYPE")
        _require(_identifier(job_id), "JOB_ID")
        _require(all(callable(x) for x in (reserve, source_check, cancelled)), "CALLBACK_TYPE")
        _require(clock_ms is None or callable(clock_ms), "CLOCK_TYPE")
        self._policy = policy
        self._job_id = job_id
        self._reserve = reserve
        self._source_check = source_check
        self._cancelled = cancelled
        self._clock = clock_ms or (lambda: time.monotonic() * 1000)
        self._last_clock: float | None = None
        try:
            self._start = self._now()
        except _Stop as exc:
            raise RecoveryTransportError(exc.code) from exc
        self._calls = 0
        self._bytes = 0
        self._invocations = 0
        self._seen: set[str] = set()
        self._reservation_ids: set[str] = set()
        self._blocked: str | None = None
        self._lock = threading.Lock()

    @property
    def policy(self) -> RecoveryTransportPolicy:
        return self._policy

    @property
    def job_id(self) -> str:
        return self._job_id

    def _now(self) -> float:
        try:
            value = self._clock()
        except Exception as exc:
            raise _Stop("CLOCK_ERROR") from exc
        if (type(value) not in (int, float) or not 0 <= value <= 2**53 - 1
                or not math.isfinite(value)
                or (self._last_clock is not None and value < self._last_clock)):
            raise _Stop("CLOCK_INVALID_OR_REGRESSED")
        self._last_clock = value
        return value

    def _guard(self, deadline: float, *, source: bool = True) -> float:
        try:
            cancelled = self._cancelled()
            if type(cancelled) is not bool:
                raise _Stop("CANCELLATION_OBSERVATION_ERROR")
            if cancelled:
                raise _Stop("CANCELLED_UNCONFIRMED")
            if source and self._source_check() is not True:
                raise _Stop("SOURCE_NOT_VERIFIED")
        except _Stop:
            raise
        except Exception as exc:
            raise _Stop("SOURCE_OR_CANCELLATION_ERROR") from exc
        # Source verification may have taken time or requested cancellation.
        try:
            cancelled = self._cancelled()
        except Exception as exc:
            raise _Stop("CANCELLATION_OBSERVATION_ERROR") from exc
        if type(cancelled) is not bool:
            raise _Stop("CANCELLATION_OBSERVATION_ERROR")
        if cancelled:
            raise _Stop("CANCELLED_UNCONFIRMED")
        now = self._now()
        if now >= deadline:
            raise _Stop("TIME_BUDGET_EXHAUSTED")
        return now

    def summary(self) -> dict:
        # A snapshot only; no fresh OS/provider observation is implied.
        return {"job_id": self.job_id, "policy_sha256": self.policy.sha256,
                "reservations_consumed": self._calls,
                "transport_invocations": self._invocations,
                "observed_response_bytes": self._bytes,
                "blocked_reason": self._blocked,
                "elapsed_ms_last_observed": self._last_clock - self._start,
                "restart_safe": False, "deadline_enforcement": DEADLINE_ENFORCEMENT}


def _payload(kind: str, payload: dict, *, native_payload: bool = False) -> bytes:
    _require(type(native_payload) is bool, "NATIVE_PAYLOAD_OPTION")
    _require(kind in (NATIVE_KINDS if native_payload else KINDS), "REQUEST_KIND")
    _require(type(payload) is dict, "PAYLOAD_OBJECT")
    raw = _canonical(payload)
    request_limit = MAX_NATIVE_REQUEST_BYTES if native_payload else MAX_REQUEST_BYTES
    _require(len(raw) <= request_limit, "REQUEST_BYTE_LIMIT")
    if kind == "MCP_SEARCH":
        basic = {"query", "num_results", "purpose"}
        bound = basic | {"run_id", "post_id", "source_receipt"}
        _require(set(payload) == basic or (native_payload and set(payload) == bound), "MCP_PAYLOAD_KEYS")
        if set(payload) == bound:
            _require(payload["purpose"] == "official_title_verify"
                     and _identifier(payload["run_id"])
                     and (type(payload["post_id"]) is int and payload["post_id"] > 0
                          or _identifier(payload["post_id"]))
                     and type(payload["source_receipt"]) is dict,
                     "MCP_SOURCE_BINDING")
        _require(type(payload["query"]) is str and bool(payload["query"].strip()), "MCP_QUERY")
        _require(type(payload["num_results"]) is int and 1 <= payload["num_results"] <= 100,
                 "MCP_NUM_RESULTS")
        _require(type(payload["purpose"]) is str, "MCP_PURPOSE")
    elif kind == "MCP_FETCH":
        _require(set(payload) == {"url", "max_length"}, "MCP_FETCH_KEYS")
        _require(type(payload["url"]) is str and payload["url"] == payload["url"].strip(), "MCP_FETCH_URL")
        try:
            url = httpx.URL(payload["url"])
            _require(url.scheme in ("http", "https") and bool(url.host)
                     and not url.userinfo and not url.fragment, "MCP_FETCH_URL")
        except (httpx.InvalidURL, UnicodeError) as exc:
            raise RecoveryTransportError("MCP_FETCH_URL") from exc
        _require(type(payload["max_length"]) is int and 0 <= payload["max_length"] <= MAX_RESPONSE_BYTES,
                 "MCP_FETCH_LENGTH")
    else:
        allowed = {"model", "messages", "stream", "max_tokens", "max_completion_tokens",
                   "temperature", "top_p", "seed", "response_format"}
        if native_payload:
            allowed |= {"min_p", "repeat_penalty", "enable_thinking", "chat_template_kwargs",
                        "repetition_penalty", "top_k", "presence_penalty"}
        _require(set(payload) <= allowed and {"model", "messages", "stream"} <= set(payload),
                 "CHAT_PAYLOAD_KEYS")
        _require(payload["stream"] is False, "CHAT_NON_STREAM_REQUIRED")
        _require(type(payload["model"]) is str and bool(payload["model"].strip()), "CHAT_MODEL")
        token_keys = set(payload) & {"max_tokens", "max_completion_tokens"}
        _require(len(token_keys) == 1, "CHAT_OUTPUT_TOKEN_LIMIT_REQUIRED")
        tokens = payload[next(iter(token_keys))]
        _require(type(tokens) is int and tokens > 0, "CHAT_OUTPUT_TOKEN_LIMIT")
        messages = payload["messages"]
        _require(type(messages) is list and bool(messages), "CHAT_MESSAGES")
        for message in messages:
            _require(type(message) is dict and set(message) == {"role", "content"}
                     and message["role"] in ("system", "user", "assistant")
                     and type(message["content"]) is str, "CHAT_MESSAGE")
        if native_payload:
            _require(tokens <= 32768, "CHAT_NATIVE_TOKEN_LIMIT")
            for key, low, high in (("temperature", 0, 2), ("top_p", 0, 1),
                                   ("min_p", 0, 1), ("repeat_penalty", 0, 2),
                                   ("presence_penalty", -2, 2)):
                if key in payload:
                    _require(type(payload[key]) in (int, float) and math.isfinite(payload[key])
                             and low <= payload[key] <= high,
                             "CHAT_NATIVE_PARAMETER")
            if "repetition_penalty" in payload:
                _require("repeat_penalty" not in payload, "CHAT_NATIVE_REPETITION_CONFLICT")
                value = payload["repetition_penalty"]
                _require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= 2,
                         "CHAT_NATIVE_REPETITION_PENALTY")
            if "top_k" in payload:
                # LLMClient의 vLLM adapter는 0/-1 설정을 요청에서 생략한다.
                _require(type(payload["top_k"]) is int and 1 <= payload["top_k"] <= 2**31-1,
                         "CHAT_NATIVE_TOP_K")
            if "seed" in payload:
                _require(type(payload["seed"]) is int and 0 <= payload["seed"] <= 2**31-1, "CHAT_NATIVE_SEED")
            if "response_format" in payload:
                _require(payload["response_format"] == {"type": "json_object"}, "CHAT_NATIVE_RESPONSE_FORMAT")
            if "enable_thinking" in payload:
                _require(type(payload["enable_thinking"]) is bool, "CHAT_NATIVE_THINKING")
            if "chat_template_kwargs" in payload:
                _require(type(payload["chat_template_kwargs"]) is dict
                         and set(payload["chat_template_kwargs"]) == {"enable_thinking"}
                         and type(payload["chat_template_kwargs"]["enable_thinking"]) is bool
                         and payload["chat_template_kwargs"]["enable_thinking"] == payload.get("enable_thinking"),
                         "CHAT_NATIVE_TEMPLATE")
    return raw


def _endpoint(value: Any) -> str:
    _require(type(value) is str and value == value.strip(), "ENDPOINT_TYPE")
    try:
        url = httpx.URL(value)
        _require(url.scheme in ("http", "https") and bool(url.host)
                 and not url.userinfo and not url.query and not url.fragment,
                 "ENDPOINT_FIXED_HTTP_URL")
    except (httpx.InvalidURL, UnicodeError) as exc:
        raise RecoveryTransportError("ENDPOINT_FIXED_HTTP_URL") from exc
    return str(url)


def _decode(raw: bytes) -> dict:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = item
        return value

    def invalid_constant(value):
        raise ValueError("nonfinite constant")

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=invalid_constant)
    _json_value(value)
    if type(value) is not dict:
        raise ValueError("response object required")
    return value


def _usage(kind: str, payload: dict | None) -> dict:
    result = {"status": "UNAVAILABLE", "source": None, "prompt_tokens": None,
              "completion_tokens": None, "total_tokens": None}
    if kind != "OPENAI_CHAT" or payload is None or payload.get("usage") is None:
        return result
    usage = payload["usage"]
    if type(usage) is not dict:
        result["status"] = "INVALID_PROVIDER_USAGE"
        return result
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    for key in keys:
        value = usage.get(key)
        if value is not None and (type(value) is not int or value < 0):
            result["status"] = "INVALID_PROVIDER_USAGE"
            return result
    for key in keys:
        result[key] = usage.get(key)
    values = [result[key] for key in keys]
    if all(value is not None for value in values) and values[0] + values[1] != values[2]:
        result["status"] = "INCONSISTENT_PROVIDER_USAGE"
    elif any(value is not None for value in values):
        result["status"] = "PROVIDER_REPORTED" if all(value is not None for value in values) else "PARTIAL"
    if any(value is not None for value in values):
        result["source"] = "PROVIDER_REPORTED"
    return result


class RecoveryTransport:
    """고정 endpoint에 POST 한 번. 실제 실행 여부 결정과 공개 판정은 맡지 않는다."""

    def __init__(self, gate: RecoveryBudgetGate, *, endpoints: Mapping[str, str],
                 headers: Mapping[str, str] | None = None,
                 test_transport: httpx.MockTransport | None = None,
                 raw_response_sink: Callable[[bytes], None] | None = None,
                 native_payload: bool = False):
        _require(type(gate) is RecoveryBudgetGate, "GATE_TYPE")
        _require(type(native_payload) is bool, "NATIVE_PAYLOAD_OPTION")
        self._native_payload = native_payload
        _require(type(endpoints) is dict and bool(endpoints)
                 and all(type(key) is str and key in (NATIVE_KINDS if native_payload else KINDS)
                         for key in endpoints), "ENDPOINT_KINDS")
        self._endpoints = MappingProxyType({key: _endpoint(value) for key, value in endpoints.items()})
        private_headers = dict(headers or {})
        _require(all(type(key) is str and key.lower() in ("authorization", "x-api-key")
                     and type(value) is str and "\r" not in value and "\n" not in value
                     for key, value in private_headers.items()), "AUTH_HEADERS_ONLY")
        private_headers.update({"Content-Type": "application/json", "Accept": "application/json",
                                "Accept-Encoding": "identity"})
        self._headers = MappingProxyType(private_headers)
        _require(test_transport is None or type(test_transport) is httpx.MockTransport,
                 "MOCK_TRANSPORT_ONLY")
        self._test_transport = test_transport
        _require(raw_response_sink is None or callable(raw_response_sink), "RAW_RESPONSE_SINK_TYPE")
        self._raw_response_sink = raw_response_sink
        self._gate = gate

    def request(self, kind: str, payload: dict, *, request_id: str) -> dict:
        _require(type(kind) is str and kind in self._endpoints, "REQUEST_KIND_NOT_CONFIGURED")
        _require(_identifier(request_id), "REQUEST_ID")
        body = _payload(kind, payload, native_payload=self._native_payload)
        endpoint = self._endpoints[kind]
        identity = {"job_id": self._gate.job_id, "request_id": request_id, "kind": kind,
                    "body_sha256": _sha(body), "endpoint_sha256": _sha(endpoint.encode()),
                    "policy_sha256": self._gate.policy.sha256}
        identity["request_sha256"] = _sha(_canonical(identity))
        gate = self._gate
        _require(gate._lock.acquire(blocking=False), "CONCURRENT_REQUEST_NOT_SUPPORTED")
        try:
            _require(request_id not in gate._seen, "REQUEST_ID_REUSED")
            gate._seen.add(request_id)
            return self._request(identity, endpoint, body)
        finally:
            gate._lock.release()

    def _request(self, identity: dict, endpoint: str, body: bytes) -> dict:
        gate = self._gate
        policy = gate.policy
        status = "SUCCESS"
        response_status = None
        reservation_id = None
        reserved = False
        invoked = False
        response_complete = False
        local_close_observed = False
        received = bytearray()
        observed_bytes = 0
        observed_hash = hashlib.sha256()
        parsed = None
        started = gate._last_clock
        deadline = gate._start + policy.max_elapsed_ms
        try:
            if gate._blocked is not None:
                raise _Stop("GATE_BLOCKED")
            started = gate._now()
            deadline = min(deadline, started + policy.request_timeout_ms)
            gate._guard(deadline)
            if gate._calls >= policy.max_calls:
                raise _Stop("CALL_BUDGET_EXHAUSTED")
            if gate._bytes >= policy.max_total_response_bytes:
                raise _Stop("OUTPUT_BUDGET_EXHAUSTED")
            gate._calls += 1  # An uncertain callback outcome cannot refund this slot.
            reserved = True
            proposal = {**identity, "schema_version": "recovery_transport_reservation_v1",
                        "ordinal": gate._calls, "elapsed_ms": gate._last_clock - gate._start,
                        "observed_response_bytes_before": gate._bytes}
            try:
                ack = gate._reserve(dict(proposal))
            except Exception as exc:
                raise _Stop("RESERVATION_CALLBACK_ERROR") from exc
            if (type(ack) is not DurableReservation or not _identifier(ack.reservation_id)
                    or type(ack.ordinal) is not int or ack.ordinal != gate._calls
                    or ack.request_sha256 != identity["request_sha256"]
                    or ack.reservation_id in gate._reservation_ids):
                raise _Stop("RESERVATION_ACK_INVALID")
            reservation_id = ack.reservation_id
            gate._reservation_ids.add(reservation_id)
            gate._guard(deadline)
            remaining_bytes = min(policy.max_response_bytes,
                                  policy.max_total_response_bytes - gate._bytes)
            # Production construction has no proxy/env/fallback/auth hooks or transport retry.
            transport = self._test_transport or httpx.HTTPTransport(retries=0, trust_env=False)
            with httpx.Client(transport=transport, trust_env=False, follow_redirects=False) as client:
                now = gate._guard(deadline)
                timeout = httpx.Timeout((deadline - now) / 1000)
                invoked = True
                gate._invocations += 1
                with client.stream("POST", endpoint, content=body, headers=dict(self._headers),
                                   timeout=timeout, follow_redirects=False) as response:
                    response_status = response.status_code
                    gate._guard(deadline)
                    encoding = response.headers.get("content-encoding", "identity").strip().lower()
                    if encoding not in ("", "identity"):
                        raise _Stop("UNSUPPORTED_CONTENT_ENCODING")
                    declared_length = response.headers.get("content-length")
                    size = None
                    if declared_length is not None:
                        try:
                            size = int(declared_length)
                        except ValueError:
                            raise _Stop("INVALID_CONTENT_LENGTH") from None
                        if size < 0:
                            raise _Stop("INVALID_CONTENT_LENGTH")
                        if size > remaining_bytes:
                            raise _Stop("RESPONSE_BYTE_LIMIT")
                    # iter_raw avoids decompression. Accumulator never contains an oversized payload.
                    for chunk in response.iter_raw(chunk_size=min(16 * 1024, remaining_bytes + 1)):
                        observed_bytes += len(chunk)
                        gate._bytes += len(chunk)
                        observed_hash.update(chunk)
                        if observed_bytes > remaining_bytes:
                            raise _Stop("RESPONSE_BYTE_LIMIT")
                        received.extend(chunk)
                        gate._guard(deadline)
                    response_complete = True
                    if size is not None and observed_bytes != size:
                        raise _Stop("CONTENT_LENGTH_MISMATCH")
            local_close_observed = True
            gate._guard(deadline)
            if not 200 <= response_status < 300:
                raise _Stop("HTTP_ERROR")
            try:
                parsed = _decode(bytes(received))
            except (UnicodeError, ValueError, RecursionError) as exc:
                raise _Stop("INVALID_JSON_RESPONSE") from exc
            gate._guard(deadline)
        except _Stop as exc:
            status = exc.code
        except httpx.TimeoutException:
            status = "TIMEOUT_UNCONFIRMED"
        except httpx.HTTPError:
            status = "TRANSPORT_ERROR_UNCONFIRMED"
        except Exception:
            # Includes local close/storage/transport implementation errors; never invent a timeout.
            status = "LOCAL_TRANSPORT_ERROR"
        # 선택 hook: 완전히 관측한 원시 bytes만 저장한다. 기존 v1 호출에는 변화가 없다.
        # 저장 실패도 전송 완료/성공으로 바꾸지 않으며 저장 시간은 아래 END 관측에 포함한다.
        if self._raw_response_sink is not None and response_complete and observed_bytes == len(received):
            try:
                self._raw_response_sink(bytes(received))
            except Exception:
                status = "RAW_RESPONSE_STORAGE_ERROR"
        # Even failure paths observe the clock after context-manager close. Do not invent an end time.
        elapsed_ms = None
        request_elapsed_ms = None
        try:
            end = gate._now()
            elapsed_ms = end - gate._start
            request_elapsed_ms = end - started
            if end >= deadline and status == "SUCCESS":
                status = "TIME_BUDGET_EXHAUSTED"
        except _Stop as exc:
            status = exc.code
        usage = _usage(identity["kind"], parsed)
        if status != "SUCCESS":
            gate._blocked = gate._blocked or status
            parsed = None
        receipt = {"schema_version": SCHEMA, **identity, "status": status,
                   "reason_codes": [] if status == "SUCCESS" else [status],
                   "transport_mode": "TEST_DOUBLE" if self._test_transport is not None else "HTTPX_SINGLE_REQUEST",
                   "reservation_id": reservation_id, "reservation_consumed": reserved,
                   "transport_invocations": int(invoked),
                   "delivery_state": "HTTP_RESPONSE_OBSERVED" if response_status is not None
                       else "POSSIBLY_SENT" if invoked else "NOT_SENT",
                   "http_status": response_status,
                   "response_complete": response_complete,
                   "response_sha256": observed_hash.hexdigest() if response_complete else None,
                   "observed_response_sha256": observed_hash.hexdigest() if observed_bytes else None,
                   "observed_response_bytes": observed_bytes,
                   "local_close_observed": local_close_observed,
                   "remote_cancel_confirmed": None,
                   "provider_completion": "UNKNOWN", "payload": parsed, "usage": usage,
                   "price": {"status": "NOT_ESTIMABLE", "amount": None},
                   "elapsed_ms": elapsed_ms, "request_elapsed_ms": request_elapsed_ms,
                   "deadline_enforcement": DEADLINE_ENFORCEMENT,
                   "time_scope": "THROUGH_LOCAL_RESPONSE_AND_CLIENT_CLOSE_OBSERVATION",
                   "gate": gate.summary(), "publication_authority": False,
                   "central_db_write": False, "public_apply": False}
        receipt["receipt_sha256"] = _sha(_canonical(receipt))
        return receipt
