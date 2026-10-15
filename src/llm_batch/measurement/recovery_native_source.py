"""저장 provider 근거를 현재 원본과 재검산해 native 재검토에 전달한다."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .recovery_provider_contract import BoundRecoveryProviderPlan
from .recovery_provider_readback import build_provider_report
from .recovery_execution_readback import read_strict_json
from ..ledger.recovery_provider_journal import canonical_bytes
from ..runtime.recovery_provider_transport import _read

_TOKEN = object()


def _require(value, code):
    if not value:
        raise ValueError(code)


class NativeProviderEvidence:
    """Factory에서 확인한 응답 원문과 원래 입력. 속성은 별도 JSON 사본이다."""

    __slots__ = ("_bound", "_report", "_raw", "_plan", "_input", "_post")

    def __init__(self, token, *, bound, report, raw, input_raw, post):
        _require(token is _TOKEN, "NATIVE_PROVIDER_FACTORY_REQUIRED")
        self._bound = bound
        self._report = canonical_bytes(report)
        self._raw = bytes(raw)
        self._plan = canonical_bytes(bound.plan)
        self._input = bytes(input_raw)
        self._post = canonical_bytes(post)

    @property
    def plan(self): return read_strict_json(self._plan)
    @property
    def report(self): return read_strict_json(self._report, maximum_bytes=len(self._report))
    @property
    def payload(self): return read_strict_json(self._raw, maximum_bytes=16 * 1024 * 1024)
    @property
    def input_post(self): return read_strict_json(self._post, maximum_bytes=len(self._post))
    @property
    def base(self): return self.plan["base"]
    @property
    def query(self): return self.plan["payload"]["query"]
    @property
    def purpose(self): return self.plan["payload"]["purpose"]
    @property
    def source_binding(self): return self.plan["source_binding"]
    @property
    def data_kind(self): return self.plan["data_kind"]
    @property
    def response_sha256(self): return hashlib.sha256(self._raw).hexdigest()

    def verify_current(self):
        _require(canonical_bytes(self._bound.plan) == self._plan, "NATIVE_PROVIDER_PLAN_CHANGED")
        current = build_provider_report(self._bound)
        _require(canonical_bytes(current) == self._report, "NATIVE_PROVIDER_REPORT_CHANGED")
        ref = current["request_receipts"][0]["response_ref"]
        path = self._bound.assert_output_path(self._bound.output_dir / ref["path"])
        _require(_read(path, ref["bytes"]) == self._raw, "NATIVE_PROVIDER_RESPONSE_CHANGED")
        return True


def read_native_provider_evidence(bound):
    """고정 provider 원장·raw 응답을 다시 읽는다. 별도 HTTP 요청을 만들지 않는다."""
    _require(type(bound) is BoundRecoveryProviderPlan, "BOUND_PROVIDER_PLAN_REQUIRED")
    report = build_provider_report(bound)
    _require(report["execution_status"] == "PROVIDER_EVIDENCE_STORED", "NATIVE_PROVIDER_NOT_COMPLETE")
    plan = bound.plan
    _require(len(plan["requests"]) == 1 and plan["requests"][0]["kind"] == "MCP_SEARCH", "NATIVE_PROVIDER_SEARCH_REQUIRED")
    _require(plan["selectors"]["input_format"] == "JSONL_POST_COMMENT_V1", "NATIVE_REQUIRES_MAIN_JSONL_INPUT")
    row = report["request_receipts"][0]
    ref = row["response_ref"]
    path = bound.assert_output_path(bound.output_dir / ref["path"])
    raw = _read(path, ref["bytes"])
    _require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], "NATIVE_PROVIDER_RAW_BINDING")
    payload = read_strict_json(raw, maximum_bytes=16 * 1024 * 1024)
    _require(type(payload) is dict and type(payload.get("results")) is list
             and all(type(item) is dict for item in payload["results"]), "NATIVE_PROVIDER_SEARCH_RESULTS")
    input_ref = plan["source_refs"]["input"]
    input_raw = _read(Path(input_ref["path"]), input_ref["bytes"])
    _require(hashlib.sha256(input_raw).hexdigest() == input_ref["sha256"], "NATIVE_INPUT_RAW_BINDING")
    # 같은 main loader의 정규화·댓글 순서·원시 오류 판정을 사용한다.
    # loader 모듈 계열의 클래스 identity를 native 코드에 전달하지 않는다.
    from expert_main import load_jsonl_posts
    posts = load_jsonl_posts(Path(input_ref["path"]), snapshot_bytes=input_raw)
    base = plan["base"]
    _require(len(posts) == base["input_count"], "NATIVE_LOADER_INPUT_COUNT")
    post = posts[base["input_index"] - 1]
    _require(type(post.post_id) is type(base["post_id"]) and post.post_id == base["post_id"], "NATIVE_LOADER_POST_BINDING")
    snapshot = {"payload": post.model_dump(mode="json"),
                "input_truncated": getattr(post, "_input_truncated", None),
                "parse_errors": list(getattr(post, "_parse_errors", ())) }
    evidence = NativeProviderEvidence(_TOKEN, bound=bound, report=report, raw=raw,
                                      input_raw=input_raw, post=snapshot)
    evidence.verify_current()
    return evidence
