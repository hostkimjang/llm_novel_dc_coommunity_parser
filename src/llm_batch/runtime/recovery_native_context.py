"""같은 호출의 pre-final native 문맥을 격리 보존하는 메모리 carrier.

디스크 역직렬화나 JSON trace의 native 승격을 제공하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import PurePath
from typing import Any

from pydantic import BaseModel

from ..domain.models import PostInput
from ..experts.orchestrator import ConversationContext

SCHEMA = "recovery_native_capture_v1"
MAX_NODES = 100_000
MAX_DEPTH = 100
MAX_BYTES = 8 * 1024 * 1024
_SEAL = object()
_RLOCK_TYPE = type(threading.RLock())
# 이 두 색인은 현재 fetch 응답의 메모리 주소에만 유효하다. 복제본은 새 fetch로만
# 다시 채운다. 이미 발행된 source_fetch_meta/후보 영수증은 일반 문맥으로 보존한다.
TRANSIENT_FETCH_IDENTITY_CACHES = frozenset({
    "_phase32_private_fetch_meta", "_private_munpia_fetch_meta",
})
_FETCH_META_KEYS = frozenset({
    "from_cache", "enumeration_finished", "error_status", "degraded",
    "possible_throttle", "attempted_count", "raw_count",
})


class NativeRecoveryError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise NativeRecoveryError(reason)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _local_type(cls):
    return cls.__module__.startswith(("llm_batch.", "src.llm_batch."))


def _attributes(value):
    attrs = dict(vars(value)) if hasattr(value, "__dict__") else {}
    if is_dataclass(value):
        for field in fields(value):
            attrs.setdefault(field.name, getattr(value, field.name))
    if isinstance(value, BaseModel):
        for name in ("__pydantic_extra__", "__pydantic_private__", "__pydantic_fields_set__"):
            attrs[name] = getattr(value, name, None)
    return attrs


def _clone_and_digest(value):
    """승인된 값만 복제한다. 사용자 copy hook/생성자/객체 reducer는 호출하지 않는다."""
    memo, encoded, active = {}, [], set()
    count = 0
    transient_bytes = 0

    def validate_transient_fetch_cache(name, cache, depth):
        """폐기할 값도 엄격히 검사한다. 일반 dict의 tuple 키는 허용하지 않는다."""
        nonlocal count, transient_bytes
        require(type(cache) is dict, "NATIVE_FETCH_CACHE_TYPE")
        count += 1
        require(count <= MAX_NODES and depth <= MAX_DEPTH, "NATIVE_CONTEXT_LIMIT")
        allowed = _FETCH_META_KEYS | ({"run_id", "post_id"} if name == "_phase32_private_fetch_meta" else set())
        for key, meta in cache.items():
            count += 3
            require(count <= MAX_NODES and depth + 2 <= MAX_DEPTH, "NATIVE_CONTEXT_LIMIT")
            require(type(key) is tuple and len(key) == 2 and type(key[0]) is str
                    and type(key[1]) is int and key[1] > 0, "NATIVE_FETCH_CACHE_KEY")
            require(type(meta) is dict, "NATIVE_FETCH_CACHE_VALUE_UNSUPPORTED")
            for field, value in meta.items():
                count += 2
                require(count <= MAX_NODES and depth + 3 <= MAX_DEPTH, "NATIVE_CONTEXT_LIMIT")
                require(type(field) is str and field in allowed, "NATIVE_FETCH_CACHE_FIELD")
                require(value is None or type(value) in (str, bool, int, float),
                        "NATIVE_FETCH_CACHE_VALUE_UNSUPPORTED")
                require(type(value) is not float or math.isfinite(value), "NATIVE_NONFINITE")
                if field in ("run_id", "post_id"):
                    require(type(value) is str, "NATIVE_FETCH_CACHE_FIELD")
            transient_bytes += len(canonical_bytes([list(key), meta]))
            require(transient_bytes <= MAX_BYTES, "NATIVE_CONTEXT_LIMIT")

    def walk(item, depth=0, path=()):
        nonlocal count
        count += 1
        require(count <= MAX_NODES and depth <= MAX_DEPTH, "NATIVE_CONTEXT_LIMIT")
        kind = type(item)
        if item is None or kind in (str, bool, int):
            return item, [kind.__name__, item]
        if kind is float:
            require(math.isfinite(item), "NATIVE_NONFINITE")
            return item, ["float", item]
        if kind is bytes:
            require(len(item) <= MAX_BYTES, "NATIVE_CONTEXT_LIMIT")
            return item, ["bytes", item.hex()]
        if isinstance(item, Enum) and _local_type(kind):
            return item, ["enum", kind.__module__, kind.__qualname__, item.name]
        if kind in (datetime, date, timedelta):
            return item, [kind.__name__, str(item)]
        if isinstance(item, PurePath):
            return item, [kind.__name__, str(item)]
        require(not callable(item), "NATIVE_CALLABLE_UNSUPPORTED")
        ident = id(item)
        require(ident not in active, "NATIVE_CONTEXT_CYCLE")
        if ident in memo:
            clone, index = memo[ident]
            return clone, ["ref", index]
        index = len(encoded)
        encoded.append(None)
        if kind is _RLOCK_TYPE:
            require(path == ("_candidate_producer_lock",), "NATIVE_LOCK_UNSUPPORTED")
            clone = threading.RLock()
            memo[ident] = (clone, index)
            encoded[index] = ["candidate_producer_rlock"]
            return clone, ["ref", index]
        active.add(ident)
        try:
            if kind in (dict, list, tuple, set, frozenset):
                clone = {} if kind is dict else [] if kind in (list, tuple) else set()
                memo[ident] = (clone, index)
                entries = []
                iterator = item.items() if kind is dict else enumerate(item)
                # set는 값의 정렬 가능한 단순 structural 표현으로 고정한다.
                if kind in (set, frozenset):
                    require(all(type(x) in (str, bool, int, float, bytes) for x in item), "NATIVE_SET_VALUE_UNSUPPORTED")
                    iterator = enumerate(sorted(item, key=lambda x: (type(x).__name__, repr(x))))
                for key, val in iterator:
                    if kind is dict:
                        require(type(key) in (str, int, bool), "NATIVE_DICT_KEY_UNSUPPORTED")
                    copied, token = walk(val, depth + 1, path + (key,))
                    if kind is dict:
                        clone[key] = copied
                        entries.append([[type(key).__name__, key], token])
                    elif kind in (list, tuple):
                        clone.append(copied); entries.append(token)
                    else:
                        clone.add(copied); entries.append(token)
                if kind is tuple:
                    clone = tuple(clone)
                elif kind is frozenset:
                    clone = frozenset(clone)
                memo[ident] = (clone, index)
                encoded[index] = [kind.__name__, entries]
            else:
                require(_local_type(kind) and (is_dataclass(item) or isinstance(item, BaseModel)), "NATIVE_OBJECT_UNSUPPORTED")
                clone = object.__new__(kind)
                memo[ident] = (clone, index)
                entries = []
                for key, val in sorted(_attributes(item).items()):
                    if kind is ConversationContext and not path and key in TRANSIENT_FETCH_IDENTITY_CACHES:
                        validate_transient_fetch_cache(key, val, depth + 1)
                        copied, token = {}, ["fetch_identity_cache_reset_v1", key]
                    else:
                        copied, token = walk(val, depth + 1, path + (key,))
                    object.__setattr__(clone, key, copied)
                    entries.append([key, token])
                encoded[index] = ["object", kind.__module__, kind.__qualname__, entries]
            return clone, ["ref", index]
        finally:
            active.remove(ident)

    clone, root = walk(value)
    raw = canonical_bytes({"root": root, "objects": encoded})
    require(len(raw) + transient_bytes <= MAX_BYTES, "NATIVE_CONTEXT_LIMIT")
    return clone, hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, init=False, repr=False)
class NativeRecoveryCapture:
    context_sha256: str
    post_sha256: str
    capture_sha256: str
    _context: Any
    _post: Any
    _post_graph_sha256: str
    _seal: Any

    @property
    def post(self):
        self.verify_current()
        return _clone_and_digest(self._post)[0]

    @property
    def post_snapshot(self):
        return self.post.model_dump(mode="json")

    @property
    def source_snapshot(self):
        post = self.post
        return {"payload": post.model_dump(mode="json"),
                "input_truncated": getattr(post, "_input_truncated", None),
                "parse_errors": list(getattr(post, "_parse_errors", ()))}

    def verify_current(self):
        require(self._seal is _SEAL, "NATIVE_CAPTURE_NOT_ISSUED")
        require(type(self._context) is ConversationContext and type(self._post) is PostInput, "NATIVE_CAPTURE_TYPE")
        for name in TRANSIENT_FETCH_IDENTITY_CACHES:
            if hasattr(self._context, name):
                cache = getattr(self._context, name)
                require(type(cache) is dict and not cache, "NATIVE_CAPTURE_TRANSIENT_CACHE_CHANGED")
        require(_clone_and_digest(self._context)[1] == self.context_sha256, "NATIVE_CONTEXT_CHANGED")
        require(_clone_and_digest(self._post)[1] == self._post_graph_sha256, "NATIVE_POST_CHANGED")
        require(sha256(self._post.model_dump(mode="json")) == self.post_sha256, "NATIVE_POST_CHANGED")
        require(self.capture_sha256 == sha256({"schema_version": SCHEMA, "context_sha256": self.context_sha256,
            "post_sha256": self.post_sha256, "post_graph_sha256": self._post_graph_sha256}), "NATIVE_CAPTURE_SHA")
        return True

    def clone_context(self):
        self.verify_current()
        return _clone_and_digest(self._context)[0]


def capture_pre_final(post, ctx):
    require(type(post) is PostInput and type(ctx) is ConversationContext, "NATIVE_INPUT_TYPE")
    require(type(ctx.post_id) is type(post.post_id) and ctx.post_id == post.post_id, "NATIVE_POST_BINDING")
    require(type(ctx.post_data) is dict and type(ctx.post_data.get("post_id")) is type(post.post_id)
        and ctx.post_data["post_id"] == post.post_id, "NATIVE_CONTEXT_POST_BINDING")
    require(ctx.post_data.get("title") == post.title, "NATIVE_CONTEXT_TITLE_BINDING")
    require(hasattr(ctx, "_final_source_original_inputs") and hasattr(ctx, "_final_source_original_comment_refs"), "NATIVE_ORIGINAL_INPUTS_MISSING")
    from ..agentic_pipeline import AgenticPipeline
    require(tuple(ctx._final_source_original_inputs) == AgenticPipeline._capture_final_source_original_inputs(post), "NATIVE_ORIGINAL_INPUTS_MISMATCH")
    require(tuple(ctx._final_source_original_comment_refs) == tuple(post.comments or ()), "NATIVE_ORIGINAL_COMMENTS_MISMATCH")
    require(not hasattr(ctx, "_final_source_projection_native"), "NATIVE_PRE_FINAL_REQUIRED")
    context, context_sha = _clone_and_digest(ctx)
    post_copy, post_graph_sha = _clone_and_digest(post)
    post_sha = sha256(post.model_dump(mode="json"))
    result = object.__new__(NativeRecoveryCapture)
    values = {"context_sha256": context_sha, "post_sha256": post_sha, "_context": context,
        "_post": post_copy, "_post_graph_sha256": post_graph_sha, "_seal": _SEAL,
        "capture_sha256": sha256({"schema_version": SCHEMA, "context_sha256": context_sha,
            "post_sha256": post_sha, "post_graph_sha256": post_graph_sha})}
    for key, value in values.items():
        object.__setattr__(result, key, value)
    result.verify_current()
    return result


@dataclass(frozen=True)
class NativeRecoveryOutcome:
    output: Any
    context: ConversationContext
    receipt: dict


def check_control(control, *, context=None):
    require(callable(getattr(control, "check", None)), "NATIVE_CONTROL_REQUIRED")
    require(control.check() is not False, "NATIVE_CONTROL_REJECTED")
    if context is not None:
        require(type(context) is ConversationContext, "NATIVE_CONTEXT_TYPE")
        setter = getattr(control, "set_context_sha256", None)
        require(callable(setter), "NATIVE_CONTEXT_BINDER_REQUIRED")
        setter(_clone_and_digest(context)[1])
        require(control.check() is not False, "NATIVE_CONTROL_REJECTED")


def evidence_pins(evidence):
    values = {"plan_sha256": evidence.plan["plan_sha256"],
              "report_sha256": evidence.report["report_sha256"],
              "response_sha256": evidence.response_sha256}
    for value in values.values():
        require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), "NATIVE_EVIDENCE_PIN_MISSING")
    return values


def require_evidence(capture, evidence):
    require(callable(getattr(evidence, "verify_current", None)) and evidence.verify_current() is True, "NATIVE_EVIDENCE_UNVERIFIED")
    post = evidence.input_post
    require(type(post) is dict and canonical_bytes(post) == canonical_bytes(capture.source_snapshot), "NATIVE_EVIDENCE_POST_MISMATCH")
    evidence_pins(evidence)
    require(type(evidence.payload) is dict and type(evidence.payload.get("results")) is list, "NATIVE_EVIDENCE_RESULTS")
    require(len(evidence.payload["results"]) <= 100 and all(type(r) is dict for r in evidence.payload["results"]), "NATIVE_EVIDENCE_LIMIT")
    require(type(evidence.query) is str and evidence.query.strip() and type(evidence.purpose) is str and evidence.purpose.strip(), "NATIVE_EVIDENCE_REQUEST")
    require(len(canonical_bytes(evidence.payload)) <= MAX_BYTES, "NATIVE_EVIDENCE_LIMIT")
    return True


def require_control_binding(control, capture, evidence):
    """원장의 최초 문맥/원본/상위 근거를 검산한다. 단계별 mutable 지문과 구별한다."""
    binding = getattr(control, "binding", None)
    require(type(binding) is dict, "NATIVE_CONTROL_BINDING_REQUIRED")
    base, report = evidence.base, evidence.report
    require(type(base) is dict and type(report) is dict, "NATIVE_CONTROL_SOURCE_BINDING")
    expected = {"context_sha256": capture.context_sha256,
                "base_sha256": sha256(base), "upstream_sha256": sha256(report)}
    for key, value in expected.items():
        require(type(binding.get(key)) is str and binding[key] == value,
                "NATIVE_CONTROL_" + key.upper() + "_MISMATCH")
    return True
