"""예약-before-send와 원시 응답 재판독을 연결한다. 재시작 자동 재전송은 없다.

actual_external_calls는 이 프로세스의 HTTP invocation만 뜻한다. 원격 MCP의
내부 검색/fallback 횟수나 원격 모델 완료/비용은 이 모듈이 확인하지 못한다.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid

from ..ledger.recovery_provider_journal import (
    RecoveryProviderJournal, RecoveryProviderJournalError, canonical_bytes,
    canonical_sha256, configuration, request_identity, require, FLAGS,
)
from ..ledger import recovery_execution_journal as files
from . import recovery_transport as transport

SCHEMA = "recovery_provider_receipt_v1"
MAX_TRANSPORT_RECEIPT_BYTES = 24 * 1024 * 1024
TIME_SCOPE = "THROUGH_REQUEST_TERMINAL_DURABLE_READBACK"


def _code(exc):
    value = getattr(exc, "code", None)
    return value if type(value) is str and 0 < len(value) <= 128 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in value) else "PROVIDER_LOCAL_ERROR"


def _read(path, maximum):
    info = files._path_info(path, label="PROVIDER_RESPONSE")
    fd = files._open_verified(path, os.O_RDONLY, expected=info, label="PROVIDER_RESPONSE", stable_snapshot=True)
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(maximum + 1)
        files._verify_handle(stream.fileno(), path, expected=info, label="PROVIDER_RESPONSE", stable_snapshot=True)
    require(len(raw) <= maximum, "RESPONSE_FILE_LIMIT")
    return raw


def _write_new(path, raw):
    # 최종 reference는 이 함수가 fsync와 readback을 모두 마친 뒤에만 반환한다.
    # 부분 파일은 원본 증거로 남고 미완결 원장이 재전송/성공을 차단한다.
    require(type(raw) is bytes, "RAW_BYTES_REQUIRED")
    files._path_info(path, label="PROVIDER_RESPONSE", missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    files._path_info(path, label="PROVIDER_RESPONSE", missing_ok=True)
    fd = files._open_verified(path, os.O_WRONLY, expected=None, label="PROVIDER_RESPONSE")
    try:
        identity = os.fstat(fd)
        offset = 0
        while offset < len(raw):
            files._verify_handle(fd, path, expected=identity, label="PROVIDER_RESPONSE")
            n = os.write(fd, raw[offset:]); require(n > 0, "RESPONSE_SHORT_WRITE")
            offset += n
        os.fsync(fd)
        files._verify_handle(fd, path, expected=identity, label="PROVIDER_RESPONSE")
    finally:
        os.close(fd)
    files._fsync_directory(path.parent)
    require(_read(path, len(raw)) == raw, "RESPONSE_READBACK_MISMATCH")


class RecoveryProviderRunner:
    """고정 plan의 직렬 요청 실행/재생. 생성자는 source/file/network I/O를 하지 않는다.

    프로세스 소유권 epoch가 달라지면 완료 재생만 허용한다. monotonic 시작점을
    새로 부여해 미완결 호출이나 다음 요청의 시간 예산을 연장하지 않는다.
    """
    def __init__(self, *, binding, policy, requests, journal_path, endpoints,
                 source_check, cancelled, headers=None, test_transport=None, clock_ms=None):
        self._binding, self._policy, self._requests = configuration(binding, policy, requests)
        require(callable(source_check) and callable(cancelled), "CALLBACK_TYPE")
        require(clock_ms is None or callable(clock_ms), "CLOCK_TYPE")
        self.journal = RecoveryProviderJournal(journal_path, binding=self._binding,
                                               policy=self._policy, requests=self._requests)
        self._source_check, self._cancelled = source_check, cancelled
        self._epoch = uuid.uuid4().hex
        self._clock = clock_ms or (lambda: time.monotonic() * 1000)
        self._start, self._last = None, None
        self._local_block = None
        self._lock = threading.Lock()
        self._mode = "TEST_DOUBLE" if test_transport is not None else "HTTPX_SINGLE_REQUEST"
        self._raw_ref = None
        self._current_identity = None
        self._request_started_elapsed_ms = None
        self._request_deadline_elapsed_ms = None
        require(type(endpoints) is dict and bool(endpoints), "ENDPOINTS_INVALID")
        self._endpoints = {k: transport._endpoint(v) for k,v in endpoints.items()}
        for request in self._requests:
            require(request["kind"] in self._endpoints, "REQUEST_ENDPOINT_MISSING")
            require(hashlib.sha256(self._endpoints[request["kind"]].encode()).hexdigest() == request["endpoint_sha256"], "REQUEST_ENDPOINT_MISMATCH")
        self._gate = transport.RecoveryBudgetGate(transport.RecoveryTransportPolicy(**self._policy),
            job_id=self._binding["plan_sha256"], reserve=self._reserve,
            source_check=self._source_guard, cancelled=self._cancel_guard, clock_ms=self._gate_clock)
        self._transport = transport.RecoveryTransport(self._gate, endpoints=self._endpoints,
            headers=headers, test_transport=test_transport, raw_response_sink=self._save_raw)

    def _now(self):
        value = self._clock()
        require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 2**53-1,
                "CLOCK_INVALID")
        require(self._last is None or value >= self._last, "CLOCK_REGRESSED")
        self._last = value
        if self._start is None:
            self._start = value
        return value

    def _gate_clock(self):
        return self._now()

    def _elapsed(self):
        return math.ceil(self._now() - self._start)

    def _cancel_guard(self):
        value = self._cancelled()
        require(type(value) is bool, "CANCELLATION_OBSERVATION_ERROR")
        return value

    def _source_guard(self):
        require(self._source_check() is True, "SOURCE_NOT_VERIFIED")
        if self._request_deadline_elapsed_ms is not None:
            self._time_guard()
        return True

    def _time_guard(self):
        elapsed = self._elapsed()
        require(elapsed < self._policy["max_elapsed_ms"], "TIME_BUDGET_EXHAUSTED")
        if self._request_deadline_elapsed_ms is not None:
            require(elapsed < self._request_deadline_elapsed_ms, "TIME_BUDGET_EXHAUSTED")

    def _guard(self):
        require(not self._cancel_guard(), "CANCELLED_UNCONFIRMED")
        self._source_guard()
        require(not self._cancel_guard(), "CANCELLED_UNCONFIRMED")
        self._time_guard()

    def _append(self, tx, state, kind, payload):
        return tx.append(expected_head_sha256=state["head_sha256"],
                         event={"event_type": kind, "elapsed_ms": self._elapsed(), "payload": payload})

    def _anchor(self, state):
        path = self.journal.path.with_name(self.journal.path.name + ".anchor.json")
        value = {"configuration_sha256": state["configuration_sha256"],
                 "journal_path_sha256": state["journal_path_sha256"], "owner_epoch": self._epoch}
        _write_new(path, canonical_bytes(value))

    def _check_anchor(self, state):
        path = self.journal.path.with_name(self.journal.path.name + ".anchor.json")
        expected = {"configuration_sha256": state["configuration_sha256"],
                    "journal_path_sha256": state["journal_path_sha256"],
                    "owner_epoch": state["started"]["payload"]["owner_epoch"]}
        require(_read(path, 4096) == canonical_bytes(expected), "JOURNAL_ANCHOR_MISMATCH")

    def _reserve(self, proposal):
        # v1 gate의 메모리 ordinal을 신뢰하지 않고 파일 상태에서 독립 계산한다.
        with self.journal.transaction() as tx:
            state = tx.snapshot()
            require(state["started"] is not None and state["started"]["payload"]["owner_epoch"] == self._epoch,
                    "RESTART_TIME_UNVERIFIED")
            self._check_anchor(state)
            self._guard()
            require(self._current_identity is not None and all(proposal.get(k) == v for k,v in self._current_identity.items()),
                    "RESERVATION_REQUEST_MISMATCH")
            require(proposal["ordinal"] == state["budget"]["reservations_consumed"] + 1, "RESERVATION_ORDINAL_INVALID")
            remaining = self._policy["max_total_response_bytes"] - state["budget"]["reserved_response_bytes"]
            allowance = self._policy["max_response_bytes"]
            require(remaining >= allowance, "OUTPUT_BUDGET_EXHAUSTED")
            require(self._request_started_elapsed_ms is not None and self._request_deadline_elapsed_ms is not None,
                    "REQUEST_DEADLINE_MISSING")
            reservation = uuid.uuid4().hex
            self._append(tx, state, "REQUEST_RESERVED", {"request_id": proposal["request_id"],
                "request_sha256": proposal["request_sha256"], "reservation_id": reservation,
                "ordinal": proposal["ordinal"], "response_bytes_reserved": allowance,
                "request_started_elapsed_ms": self._request_started_elapsed_ms,
                "request_deadline_elapsed_ms": self._request_deadline_elapsed_ms})
            return transport.DurableReservation(reservation, proposal["request_sha256"], proposal["ordinal"])

    def _store(self, raw, suffix):
        identity = self._current_identity
        require(identity is not None, "REQUEST_CONTEXT_MISSING")
        name = identity["request_sha256"] + suffix
        path = self.journal.path.parent / "responses" / name
        _write_new(path, raw)
        return {"path": "responses/" + name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    def _save_raw(self, raw):
        self._raw_ref = self._store(raw, ".bin")

    def _read_ref(self, ref, maximum):
        from ..ledger.recovery_provider_journal import _ref
        _ref(ref)
        require(ref["bytes"] <= maximum, "RESPONSE_FILE_LIMIT")
        raw = _read(self.journal.path.parent / ref["path"], maximum)
        require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], "RESPONSE_FILE_SHA_MISMATCH")
        return raw

    def _stored(self, state, request_id, *, allow_unfinalized=False):
        call = state["calls"][request_id]
        terminal, final = call["terminal"], call["finalized"]
        require(terminal is not None and (final is not None or allow_unfinalized), "INCOMPLETE_DISPATCH")
        payload = terminal["payload"]
        raw_receipt = self._read_ref(payload["transport_ref"], MAX_TRANSPORT_RECEIPT_BYTES)
        tr = transport._decode(raw_receipt)
        require(canonical_bytes(tr) == raw_receipt, "TRANSPORT_RECEIPT_CANONICAL_MISMATCH")
        require(tr.get("receipt_sha256") == payload["transport_receipt_sha256"]
                == canonical_sha256({k:v for k,v in tr.items() if k != "receipt_sha256"}), "TRANSPORT_RECEIPT_SHA_MISMATCH")
        request = next(r for r in self._requests if r["request_id"] == request_id)
        identity = request_identity(self._binding, self._policy, request)
        require(all(tr.get(k) == v for k,v in identity.items()), "TRANSPORT_REQUEST_MISMATCH")
        require(tr.get("schema_version") == transport.SCHEMA
                and tr.get("transport_mode") == state["started"]["payload"]["transport_mode"], "TRANSPORT_SCHEMA_MODE_MISMATCH")
        require(tr.get("reservation_id") == call["reserved"]["payload"]["reservation_id"]
                and tr.get("reservation_consumed") is True, "TRANSPORT_RESERVATION_MISMATCH")
        require(tr.get("status") == payload["status"]
                and type(tr.get("transport_invocations")) is int
                and type(tr.get("observed_response_bytes")) is int
                and tr.get("transport_invocations") == payload["transport_invocations"]
                and tr.get("observed_response_bytes") == payload["observed_response_bytes"], "TRANSPORT_TERMINAL_MISMATCH")
        require(all(tr.get(k) is False for k in FLAGS), "TRANSPORT_AUTHORITY_MISMATCH")
        ref = payload["response_ref"]
        response_raw = None
        if ref is not None:
            require(ref["path"] == "responses/" + identity["request_sha256"] + ".bin", "RESPONSE_REQUEST_PATH_MISMATCH")
            response_raw = self._read_ref(ref, self._policy["max_response_bytes"])
            require(tr.get("response_complete") is True and ref["sha256"] == tr.get("response_sha256")
                    and tr.get("observed_response_sha256") == (ref["sha256"] if ref["bytes"] else None)
                    and ref["bytes"] == tr.get("observed_response_bytes"),
                    "RAW_TRANSPORT_BINDING_MISMATCH")
        require(payload["transport_ref"]["path"] == "responses/" + identity["request_sha256"] + ".json", "TRANSPORT_REQUEST_PATH_MISMATCH")
        status = final["payload"]["status"] if final is not None else payload["status"]
        if status == "SUCCESS":
            require(response_raw is not None and canonical_bytes(transport._decode(response_raw)) == canonical_bytes(tr.get("payload")),
                    "RAW_PAYLOAD_MISMATCH")
        reasons = final["payload"]["reason_codes"] if final is not None else tr["reason_codes"]
        return tr, ref, status, reasons

    def _receipt(self, *, request_id, state=None, status, reasons, replayed=False, tr=None, ref=None, invocations=0):
        request = next((r for r in self._requests if r["request_id"] == request_id), None)
        actual = invocations if self._mode == "HTTPX_SINGLE_REQUEST" else 0
        call = state["calls"].get(request_id) if state and type(request_id) is str else None
        terminal = call["terminal"]["payload"] if call and call["terminal"] else None
        value = {"schema_version": SCHEMA, "status": status, "reason_codes": reasons,
            "request_id": request_id, "request_sha256": request_identity(self._binding, self._policy, request)["request_sha256"] if request else None,
            "binding": deepcopy(self._binding), "policy_sha256": self._binding["policy_sha256"],
            "journal_head_sha256": state["head_sha256"] if state else None,
            "transport_receipt": tr, "response_ref": ref, "payload": deepcopy(tr["payload"]) if status == "SUCCESS" and tr else None,
            "transport_ref": deepcopy(terminal["transport_ref"]) if terminal else None,
            "transport_receipt_sha256": terminal["transport_receipt_sha256"] if terminal else None,
            "reservation_id": call["reserved"]["payload"]["reservation_id"] if call else None,
            "replayed": replayed, "transport_mode": self._mode, "transport_invocations": invocations,
            "transport_invocations_this_invocation": invocations,
            "evidence_mode": "TEST_SYNTHETIC_TRANSPORT" if self._mode == "TEST_DOUBLE" else "PROVIDER_HTTP_OBSERVATION",
            "actual_external_calls": actual, "actual_external_call_scope": "LOCAL_HTTP_INVOCATIONS_ONLY",
            "remote_dispatch_count": None, "remote_dispatch_status": "UNKNOWN",
            "provider_completion": "UNKNOWN", "remote_cancel_confirmed": None,
            "price": {"status": "NOT_ESTIMABLE", "amount": None},
            "budget": deepcopy(state["budget"]) if state else None, "restart_safe": True,
            "restart_policy": "COMPLETED_REPLAY_ONLY_OTHERWISE_FAIL_CLOSED", "retry_count": 0,
            "time_scope": TIME_SCOPE, "finalization_write_in_time_scope": False, **FLAGS}
        value["receipt_sha256"] = canonical_sha256(value)
        return value

    def readback(self, *, request_id):
        """전송·lock·원장 쓰기 없이 완료 원문/receipt/결속을 재판독한다."""
        state = None
        try:
            require(type(request_id) is str and any(r["request_id"] == request_id for r in self._requests), "REQUEST_NOT_PLANNED")
            state = self.journal.snapshot()
            if state["started"] is None:
                anchor = self.journal.path.with_name(self.journal.path.name + ".anchor.json")
                require(files._path_info(anchor, label="PROVIDER_ANCHOR", missing_ok=True) is None, "JOURNAL_MISSING_AFTER_ANCHOR")
                return self._receipt(request_id=request_id, state=state, status="NOT_STARTED", reasons=["REQUEST_NOT_STARTED"], replayed=True)
            self._check_anchor(state)
            require(state["started"]["payload"]["transport_mode"] == self._mode, "TRANSPORT_MODE_MISMATCH")
            self._source_guard()
            if request_id not in state["calls"]:
                return self._receipt(request_id=request_id, state=state, status="NOT_STARTED", reasons=["REQUEST_NOT_STARTED"], replayed=True)
            tr, ref, status, reasons = self._stored(state, request_id)
            return self._receipt(request_id=request_id, state=state, status=status, reasons=reasons, replayed=True, tr=tr, ref=ref)
        except Exception as exc:
            return self._receipt(request_id=request_id if type(request_id) is str else None, state=state,
                status="INCOMPLETE" if state and state["open_request_id"] else "NOT_AVAILABLE",
                reasons=[_code(exc)], replayed=True)

    def request(self, kind, payload, *, request_id):
        require(self._lock.acquire(blocking=False), "CONCURRENT_REQUEST_NOT_SUPPORTED")
        state, tr, invocations = None, None, 0
        try:
            request = next((r for r in self._requests if r["request_id"] == request_id), None)
            require(request is not None and kind == request["kind"], "REQUEST_NOT_PLANNED")
            body = transport._payload(kind, payload)
            require(hashlib.sha256(body).hexdigest() == request["body_sha256"], "REQUEST_BODY_MISMATCH")
            self._current_identity = request_identity(self._binding, self._policy, request)
            state = self.journal.snapshot()
            if state["started"]:
                self._check_anchor(state)
                require(state["started"]["payload"]["transport_mode"] == self._mode, "TRANSPORT_MODE_MISMATCH")
            if request_id in state["calls"] and state["calls"][request_id]["finalized"] is not None:
                self._source_guard()
                tr, ref, status, reasons = self._stored(state, request_id)
                return self._receipt(request_id=request_id, state=state, status=status, reasons=reasons,
                                     replayed=True, tr=tr, ref=ref)
            require(self._local_block is None, "RUNNER_BLOCKED")
            require(state["open_request_id"] is None, "INCOMPLETE_DISPATCH")
            require(state["blocked_reason"] is None, "JOB_BLOCKED")
            if state["started"]:
                require(state["started"]["payload"]["owner_epoch"] == self._epoch, "RESTART_TIME_UNVERIFIED")
            # 완료 재생에는 새 마감을 부여하지 않는다. 새 실행은 첫 fresh guard 전에
            # 시작점을 고정하므로 source 검사/원장 lock/예약 저장 시간도 포함한다.
            # 시작은 내림, 종료는 올림해 정수 ms 변환으로 예산이 늘어나지 않게 한다.
            self._request_started_elapsed_ms = math.floor(self._now() - self._start)
            self._request_deadline_elapsed_ms = min(self._policy["max_elapsed_ms"],
                self._request_started_elapsed_ms + self._policy["request_timeout_ms"])
            self._guard()
            # 0 예산은 lock/anchor/원장/transport를 만들지 않는다.
            require(state["budget"]["reservations_consumed"] < self._policy["max_calls"], "CALL_BUDGET_EXHAUSTED")
            require(state["budget"]["reserved_response_bytes"] + self._policy["max_response_bytes"] <= self._policy["max_total_response_bytes"], "OUTPUT_BUDGET_EXHAUSTED")
            if state["started"] is None:
                with self.journal.transaction() as tx:
                    state = tx.snapshot()
                    require(state["started"] is None, "CONCURRENT_JOB_STARTED")
                    self._guard()
                    self._anchor(state)
                    self._append(tx, state, "JOB_STARTED", {"owner_epoch": self._epoch, "transport_mode": self._mode})
            self._raw_ref = None
            tr = self._transport.request(kind, json.loads(body), request_id=request_id)
            invocations = tr["transport_invocations"]
            state = self.journal.snapshot()
            call = state["calls"].get(request_id)
            if call is None:
                # 예약 전 실패는 완료 event를 위조하지 않는다.
                self._local_block = tr["status"]
                return self._receipt(request_id=request_id, state=state, status=tr["status"], reasons=[tr["status"]], tr=tr, invocations=invocations)
            require(tr["reservation_id"] == call["reserved"]["payload"]["reservation_id"], "RESERVATION_ACK_NOT_ESTABLISHED")
            tr_raw = canonical_bytes(tr)
            require(len(tr_raw) <= MAX_TRANSPORT_RECEIPT_BYTES, "TRANSPORT_RECEIPT_BYTE_LIMIT")
            tr_ref = self._store(tr_raw, ".json")
            with self.journal.transaction() as tx:
                state = tx.snapshot()
                if tr["status"] == "SUCCESS":
                    self._time_guard()
                terminal = self._append(tx, state, "REQUEST_TERMINAL", {"request_id": request_id,
                    "status": tr["status"], "response_ref": self._raw_ref, "transport_ref": tr_ref,
                    "transport_receipt_sha256": tr["receipt_sha256"], "observed_response_bytes": tr["observed_response_bytes"],
                    "transport_invocations": invocations, "actual_external_calls": invocations if self._mode == "HTTPX_SINGLE_REQUEST" else 0})
                state = tx.snapshot()
                # 원시 응답과 transport receipt의 독립 재판독도 성공 확정 전에 수행한다.
                tr, ref, status, reasons = self._stored(state, request_id, allow_unfinalized=True)
                reasons = list(reasons)
                if status == "SUCCESS":
                    try:
                        self._guard()
                        require(self._elapsed() < state["calls"][request_id]["reserved"]["payload"]["request_deadline_elapsed_ms"], "TIME_BUDGET_EXHAUSTED")
                    except Exception as exc:
                        status, reasons = _code(exc), [_code(exc)]
                self._append(tx, state, "REQUEST_FINALIZED", {"request_id": request_id,
                    "terminal_sha256": terminal["event_sha256"], "status": status, "reason_codes": reasons})
                state = tx.snapshot()
            if status != "SUCCESS":
                self._local_block = status
            return self._receipt(request_id=request_id, state=state, status=status, reasons=reasons,
                                 tr=tr, ref=ref, invocations=invocations)
        except Exception as exc:
            reason = _code(exc)
            self._local_block = self._local_block or reason
            try:
                state = self.journal.snapshot()
            except Exception:
                state = None
            return self._receipt(request_id=request_id if type(request_id) is str else None,
                state=state, status="INCOMPLETE" if state and state["open_request_id"] else "NOT_AVAILABLE",
                reasons=[reason], invocations=invocations)
        finally:
            self._current_identity = None
            self._request_started_elapsed_ms = None
            self._request_deadline_elapsed_ms = None
            self._lock.release()
