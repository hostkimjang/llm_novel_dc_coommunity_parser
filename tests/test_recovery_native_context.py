"""same-call native 문맥 보존·소유권·전문가 소비 경계. 외부 I/O는 없다."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import hashlib
import json
import threading

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext, ExpertMessage, ExpertType, Orchestrator
from llm_batch.runtime import recovery_native_context as native
from test_candidate_retrieval_pipeline import FakeLLM, FakeMCP, _pipeline, _post, _public, no_external_or_extra_runtime


def make_context(post=None):
    post = post or _post()
    ctx = ConversationContext(post_id=post.post_id, post_data={"post_id": post.post_id,
        "title": post.title, "content_blocks": [b.model_dump() for b in post.content_blocks]}, comments=["댓글"])
    ctx._final_source_original_inputs = AgenticPipeline._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments or ())
    ctx.expert_outputs = {"gatekeeper": {"is_noise": False}, "discourse": {"discourse_analysis": {
        "primary_domain": "novel_work", "intent": "discussion"}}, "arbiter": {"stale": True}}
    ctx.messages = [ExpertMessage(ExpertType.ARBITER, None, "analysis", {"stale": True})]
    shared = {"text": "원문 보존"}
    ctx.shared_a = shared
    ctx.shared_b = [shared]
    ctx._processed_requests = {"verifier::decoder"}
    return post, ctx


def evidence(capture):
    return SimpleNamespace(verify_current=lambda: True, input_post=capture.source_snapshot,
        plan={"plan_sha256": "a" * 64}, report={"report_sha256": "b" * 64},
        base={"post_id": capture.post.post_id, "publication_scope_id": "d" * 64},
        response_sha256="c" * 64, query="고정 원문 검색", purpose="image_ocr_diagnostic_probe",
        source_binding={"post_id": capture.post.post_id}, payload={"results": [
            {"title": "후보", "url": "https://example.invalid/work", "content": "검색 원문",
             "official_title_exists": True, "_official_detail_verified": True}]})


def test_capture_clones_lock_aliases_and_original_occurrences():
    post, ctx = make_context()
    capture = native.capture_pre_final(post, ctx)
    clone = capture.clone_context()
    assert clone is not ctx
    assert clone._candidate_producer_lock is not ctx._candidate_producer_lock
    assert clone.shared_a is clone.shared_b[0] and clone.shared_a is not ctx.shared_a
    assert clone._final_source_original_inputs == ctx._final_source_original_inputs
    assert clone._final_source_original_comment_refs == tuple(post.comments)
    clone.shared_a["text"] = "복구만 수정"
    clone._final_source_original_comment_refs[0]["content"] = "복구 댓글"
    assert ctx.shared_a["text"] == "원문 보존"
    assert post.comments[0]["content"] != "복구 댓글"
    assert capture.verify_current() is True
    assert capture.clone_context().shared_a["text"] == "원문 보존"


def test_capture_survives_normal_base_context_mutation_but_private_checkpoint_tamper_fails():
    post, ctx = make_context()
    capture = native.capture_pre_final(post, ctx)
    ctx.expert_outputs["arbiter"] = {"final_decision": {"is_relevant": False}}
    assert capture.verify_current() is True
    with pytest.raises(FrozenInstanceError):
        capture.context_sha256 = "0" * 64
    capture._context.shared_a["text"] = "봉인 뒤 오염"
    with pytest.raises(native.NativeRecoveryError, match="NATIVE_CONTEXT_CHANGED"):
        capture.clone_context()


def test_post_and_source_snapshot_are_defensive_copies_with_loader_flags():
    post, ctx = make_context()
    object.__setattr__(post, "_input_truncated", True)
    object.__setattr__(post, "_parse_errors", ["source error"])
    capture = native.capture_pre_final(post, ctx)
    exposed = capture.post
    exposed.title = "바뀐 제목"
    snapshot = capture.source_snapshot
    snapshot["parse_errors"].append("다른 오류")
    assert capture.post.title == post.title
    assert capture.source_snapshot["input_truncated"] is True
    assert capture.source_snapshot["parse_errors"] == ["source error"]
    bound = evidence(capture)
    assert native.require_evidence(capture, bound) is True
    bound.input_post["input_truncated"] = False
    with pytest.raises(native.NativeRecoveryError, match="POST_MISMATCH"):
        native.require_evidence(capture, bound)


@pytest.mark.parametrize("fault", ["callback", "unknown", "cycle", "lock", "nonfinite", "source", "post", "final"])
def test_capture_rejects_unsupported_or_unbound_state(fault):
    post, ctx = make_context()
    if fault == "callback": ctx.bad = lambda: None
    elif fault == "unknown": ctx.bad = SimpleNamespace(value=1)
    elif fault == "cycle": ctx.bad = ctx
    elif fault == "lock": ctx.bad = threading.RLock()
    elif fault == "nonfinite": ctx.bad = float("nan")
    elif fault == "source": ctx._final_source_original_inputs = ()
    elif fault == "post": ctx.post_id += 1
    else: ctx._final_source_projection_native = object()
    with pytest.raises(native.NativeRecoveryError):
        native.capture_pre_final(post, ctx)


def test_capture_depth_bound_is_checked_without_mutating_original(monkeypatch):
    post, ctx = make_context()
    ctx.bad = [[[[[["too deep"]]]]]]
    monkeypatch.setattr(native, "MAX_DEPTH", 3)
    with pytest.raises(native.NativeRecoveryError, match="LIMIT"):
        native.capture_pre_final(post, ctx)
    assert ctx.bad == [[[[[["too deep"]]]]]]


class FreshNativeFetch:
    """실제 Orchestrator fetch producer에 넘기는 로컬 응답. 네트워크는 없다."""
    def __init__(self):
        self.results = []

    def fetch(self, url):
        raise AssertionError("metadata-aware fetch must be used")

    def _fetch_with_meta(self, url):
        result = {"url": url, "text": "합성 원문", "structured_info": {"title": "합성 작품"}}
        self.results.append(result)
        return result, {"from_cache": False, "enumeration_finished": True,
            "error_status": "NONE", "degraded": False, "possible_throttle": False,
            "attempted_count": 1, "raw_count": 1}


def test_capture_resets_actual_fetch_identity_indexes_without_reusing_freshness_or_losing_receipts(tmp_path):
    from copy import deepcopy
    post, ctx = make_context()
    source = FreshNativeFetch()
    orchestrator = Orchestrator({}, fetch_fn=source.fetch, page_cache_dir=tmp_path / "cache",
        page_cache_enabled=False, monitor_enabled=False)
    url = "https://www.munpia.com/novel/detail/123"
    fetched = orchestrator._fetch_with_context_receipt(ctx, url, purpose="source_bound_direct_detail")
    original_entry = orchestrator._phase32_fetched_entry(ctx, url, fetched, "합성 미리보기")
    assert original_entry["source_fetch_meta"]["from_cache"] is False
    assert all((url, id(fetched)) in getattr(ctx, name) for name in native.TRANSIENT_FETCH_IDENTITY_CACHES)
    ctx.fetched_page_info = [original_entry]
    original_indexes = {name: deepcopy(getattr(ctx, name)) for name in native.TRANSIENT_FETCH_IDENTITY_CACHES}
    original_source_meta = deepcopy(ctx._source_bound_direct_fetch_meta)
    capture = native.capture_pre_final(post, ctx)
    clone = capture.clone_context()
    for name in native.TRANSIENT_FETCH_IDENTITY_CACHES:
        assert getattr(clone, name) == {} and getattr(capture._context, name) == {}
        assert getattr(ctx, name) == original_indexes[name]
    assert clone.fetched_page_info == [original_entry]
    assert clone.fetched_page_info[0] is not original_entry
    assert clone._source_bound_direct_fetch_meta == original_source_meta
    assert clone._candidate_producer_receipts == ctx._candidate_producer_receipts
    # 원래 응답 객체를 clone의 소비자에 다시 넣어도 이전 fresh 권한은 되살아나지 않는다.
    assert "source_fetch_meta" not in orchestrator._phase32_fetched_entry(clone, url, fetched, "같은 원문")
    newly_fetched = orchestrator._fetch_with_context_receipt(clone, url, purpose="source_bound_direct_detail")
    assert newly_fetched is not fetched
    new_entry = orchestrator._phase32_fetched_entry(clone, url, newly_fetched, "새 관측")
    assert new_entry["source_fetch_meta"]["from_cache"] is False
    assert all((url, id(newly_fetched)) in getattr(clone, name) for name in native.TRANSIENT_FETCH_IDENTITY_CACHES)
    assert all(getattr(ctx, name) == original_indexes[name] for name in original_indexes)
    assert capture.verify_current() and capture.clone_context().fetched_page_info == [original_entry]


@pytest.mark.parametrize("name", sorted(native.TRANSIENT_FETCH_IDENTITY_CACHES))
def test_transient_cache_identity_is_not_hashed_as_reusable_authority_and_sealed_mutation_fails(name):
    post, ctx = make_context()
    meta = {"from_cache": False, "enumeration_finished": True, "error_status": "NONE"}
    setattr(ctx, name, {("https://example.invalid/detail", 1234): dict(meta)})
    first = native.capture_pre_final(post, ctx)
    setattr(ctx, name, {("https://example.invalid/detail", 5678): dict(meta)})
    second = native.capture_pre_final(post, ctx)
    assert first.context_sha256 == second.context_sha256
    assert native._clone_and_digest(first.clone_context())[1] == first.context_sha256
    getattr(first._context, name)[("https://example.invalid/detail", 1234)] = meta
    with pytest.raises(native.NativeRecoveryError, match="NATIVE_CAPTURE_TRANSIENT_CACHE_CHANGED"):
        first.verify_current()


@pytest.mark.parametrize("name", sorted(native.TRANSIENT_FETCH_IDENTITY_CACHES))
@pytest.mark.parametrize("fault", ["bad_key", "bool_id", "callback", "custom", "cycle", "nonfinite", "unknown_field", "subclass"])
def test_reset_does_not_hide_unsupported_fetch_cache_state(name, fault):
    post, ctx = make_context()
    key = ("https://example.invalid/detail", 1234)
    meta = {"from_cache": False}
    if fault == "bad_key": key = (key[0], key[1], "extra")
    elif fault == "bool_id": key = (key[0], True)
    elif fault == "callback": meta["error_status"] = lambda: None
    elif fault == "custom": meta["error_status"] = SimpleNamespace(value=1)
    elif fault == "cycle": meta["error_status"] = meta
    elif fault == "nonfinite": meta["raw_count"] = float("inf")
    elif fault == "unknown_field": meta["invented_authority"] = True
    else:
        class Cache(dict):
            pass
        setattr(ctx, name, Cache({key: meta}))
    if fault != "subclass": setattr(ctx, name, {key: meta})
    original = getattr(ctx, name)
    with pytest.raises(native.NativeRecoveryError):
        native.capture_pre_final(post, ctx)
    assert getattr(ctx, name) is original


def test_tuple_keys_remain_unsupported_outside_declared_transient_caches():
    post, ctx = make_context()
    ctx.other_map = {("url", 1234): {"from_cache": False}}
    with pytest.raises(native.NativeRecoveryError, match="NATIVE_DICT_KEY_UNSUPPORTED"):
        native.capture_pre_final(post, ctx)


def test_discarded_fetch_cache_still_counts_toward_capture_size_bound(monkeypatch):
    post, ctx = make_context()
    ctx._phase32_private_fetch_meta = {("https://example.invalid/detail", 1234): {"error_status": "x" * 4096}}
    monkeypatch.setattr(native, "MAX_BYTES", 2048)
    with pytest.raises(native.NativeRecoveryError, match="NATIVE_CONTEXT_LIMIT"):
        native.capture_pre_final(post, ctx)
    assert len(ctx._phase32_private_fetch_meta[("https://example.invalid/detail", 1234)]["error_status"]) == 4096


def test_real_process_optional_capture_preserves_public_result_and_expert_calls(tmp_path):
    baseline, llm0, mcp0 = _pipeline(tmp_path / "baseline")
    instrumented, llm1, mcp1 = _pipeline(tmp_path / "capture")
    post = _post()
    expected = baseline.process_post(post)
    actual, capture = instrumented.process_post_with_recovery_context(post)
    assert _public(actual) == _public(expected)
    assert llm0.calls == llm1.calls and mcp0.calls == mcp1.calls
    assert type(capture) is native.NativeRecoveryCapture and capture.verify_current()
    assert "NativeRecoveryCapture" not in json.dumps(actual.model_dump())


def test_failing_capture_sink_does_not_change_normal_process(tmp_path):
    baseline, llm0, mcp0 = _pipeline(tmp_path / "baseline")
    instrumented, llm1, mcp1 = _pipeline(tmp_path / "failed")
    post = _post()
    def sink(*args):
        raise RuntimeError("capture unavailable")
    expected = baseline.process_post(post)
    actual = instrumented.process_post(post, native_context_sink=sink)
    assert _public(actual) == _public(expected)
    assert llm0.calls == llm1.calls and mcp0.calls == mcp1.calls


class StageExpert:
    def __init__(self, role, calls, control):
        self.role, self.calls, self.control = role, calls, control
        self.llm = control.llm

    def analyze(self, *args, **kwargs):
        ctx = kwargs.get("ctx") or args[0]
        self.calls.append((self.role, ctx))
        if self.role == "verifier" and getattr(self.control, "poison_verifier", False):
            self.control.failed = True
            return {"error": "provider response unavailable"}
        return {"stage": self.role}


def control_case(capture=None, evidence_value=None):
    if capture is None:
        capture = native.capture_pre_final(*make_context())
    evidence_value = evidence_value or evidence(capture)
    binding = {"context_sha256": capture.context_sha256,
        "base_sha256": native.sha256(evidence_value.base),
        "upstream_sha256": native.sha256(evidence_value.report),
        "source_sha256": "e" * 64, "config_sha256": "f" * 64}
    control = SimpleNamespace(llm=FakeLLM(), mcp=FakeMCP(), failed=False, context_hashes=[], binding=binding)
    control.set_context_sha256 = control.context_hashes.append
    def check():
        if control.failed:
            raise native.NativeRecoveryError("STICKY_IO_FAILURE")
    control.check = check
    return control


def test_explicit_recheck_consumes_one_owned_ctx_in_required_order(tmp_path, monkeypatch):
    post, original = make_context()
    capture = native.capture_pre_final(post, original)
    ctx = capture.clone_context()
    control, calls = control_case(), []
    experts = {role: StageExpert(role.value, calls, control) for role in (
        ExpertType.DECODER, ExpertType.VERIFIER, ExpertType.SYNTHESIZER, ExpertType.ARBITER)}
    orchestrator = Orchestrator(experts, page_cache_dir=tmp_path / "cache", page_cache_enabled=False,
        monitor_enabled=False, fetch_concurrency=1)
    monkeypatch.setattr(orchestrator, "_probe_verified_candidate_official_detail", lambda *args: None)
    monkeypatch.setattr(orchestrator, "_guard_synthesizer_override", lambda current: calls.append(("synthesis_guard", current)))
    result = orchestrator.recheck_context(ctx, {}, control=control)
    assert result is ctx
    assert [r for r, c in calls] == ["decoder", "verifier", "synthesizer", "synthesis_guard", "arbiter"]
    assert all(c is ctx for r, c in calls)
    assert all(not m.content.get("stale") for m in ctx.messages)
    assert original.expert_outputs["arbiter"] == {"stale": True}
    assert not (tmp_path / "cache").exists()
    assert capture.verify_current()
    assert len(control.context_hashes) >= 10 and len(set(control.context_hashes)) > 1
    assert control.context_hashes[-1] == native._clone_and_digest(ctx)[1]


def test_native_constructor_requires_explicit_dependencies_without_shared_cache(tmp_path, monkeypatch):
    import llm_batch.agentic_pipeline as module
    monkeypatch.setattr(module, "GatekeeperExpert", lambda llm: SimpleNamespace(llm=llm))
    llm, mcp = FakeLLM(), FakeMCP()
    with pytest.raises(ValueError, match="explicit"):
        AgenticPipeline(llm=llm, native_recovery=True, output_dir=tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()
    pipe = AgenticPipeline(llm=llm, mcp=mcp, output_dir=tmp_path / "attempt", native_recovery=True)
    assert pipe.llm is llm and pipe.mcp is mcp
    assert not pipe._use_session_knowledge and not pipe.batch_context.enabled
    assert not pipe.enable_active_learning_queue and not pipe.enable_url_fetch_disk_cache
    assert pipe.orchestrator.page_analyzer_cache_dir == tmp_path / "attempt" / "page_analyzer_cache"
    assert not pipe.orchestrator.page_analyzer_cache_dir.exists()
    assert pipe.orchestrator._monitor_enabled is False


def test_pipeline_sticky_failure_after_real_verifier_stops_without_output_or_base_mutation(tmp_path, monkeypatch):
    import llm_batch.agentic_pipeline as module
    monkeypatch.setattr(module, "GatekeeperExpert", lambda llm: SimpleNamespace(llm=llm))
    post, ctx = make_context()
    capture = native.capture_pre_final(post, ctx)
    control, calls = control_case(capture), []
    control.poison_verifier = True
    pipe = AgenticPipeline(llm=control.llm, mcp=control.mcp, output_dir=tmp_path, native_recovery=True)
    pipe.experts = {role: StageExpert(role.value, calls, control) for role in (
        ExpertType.DECODER, ExpertType.VERIFIER, ExpertType.SYNTHESIZER, ExpertType.ARBITER)}
    pipe.orchestrator.experts = pipe.experts
    monkeypatch.setattr(pipe.orchestrator, "_probe_verified_candidate_official_detail", lambda *args: None)
    with pytest.raises(native.NativeRecoveryError, match="STICKY"):
        pipe.continue_native_recovery(capture, evidence(capture), control)
    assert [role for role, _ in calls] == ["decoder", "verifier"]
    owned = calls[0][1]
    assert owned is not ctx
    assert "official_title_exists" not in owned.search_results[0]
    assert "_official_detail_verified" not in owned.search_results[0]
    assert owned.search_results[0]["_ocr_diagnostic_only"] is True
    assert pipe.orchestrator._active_ctx is None
    assert not hasattr(pipe.orchestrator, "_last_ctx")
    assert capture.verify_current()
    assert ctx.expert_outputs["arbiter"] == {"stale": True} and ctx.search_results == []
    with pytest.raises(native.NativeRecoveryError, match="ALREADY_CONSUMED"):
        pipe.continue_native_recovery(capture, evidence(capture), control)


class CapturingSynthesisLLM(FakeLLM):
    max_tokens = 2048
    stream = False
    backend = "local"

    def __init__(self, *, fail=False):
        super().__init__()
        self.prompts = []
        self.fail = fail

    def _stream_chat_http(self, *, messages, tag, **kwargs):
        assert tag == "synthesizer"
        self.prompts.append(messages[-1]["content"])
        if self.fail:
            raise RuntimeError("synthetic synthesis failure")
        self.last_usage_provenance = "PROVIDER_REPORTED"
        self.last_finish_reason = "stop"
        return json.dumps({"synthesis_summary": "검색 원문만 정리",
            "confidence_assessment": {"is_about_identified_work": False, "confidence": "Low"},
            "evidence_alignment": {"decoder_match": "weak", "verifier_match": "weak",
                                   "overall_coherence": "low"}, "hidden_references": []}, ensure_ascii=False)


@pytest.mark.parametrize("marker", ["flag", "purpose", "both"])
@pytest.mark.parametrize("fail", [False, True])
def test_native_real_synthesizer_prompt_excludes_diagnostic_hits_and_restores_history(tmp_path, marker, fail):
    from copy import deepcopy
    from llm_batch.experts.synthesizer import SynthesizerExpert
    post, ctx = make_context()
    diagnostic = {"title": "진단전용반례작품", "url": "https://example.invalid/diagnostic",
                  "content": "진단전용검색본문유일값", "_evidence_id": "E901"}
    if marker in {"flag", "both"}:
        diagnostic["_ocr_diagnostic_only"] = True
    if marker in {"purpose", "both"}:
        diagnostic["_purpose"] = "image_ocr_diagnostic_probe"
    ordinary = {"title": "독립검색근거작품", "url": "https://example.invalid/ordinary",
                "content": "독립검색본문유일값", "_evidence_id": "E902", "_purpose": "verify"}
    ctx.search_results = [diagnostic, ordinary]
    history = ctx.search_results
    before = deepcopy(history)
    control, calls = control_case(), []
    control.llm = CapturingSynthesisLLM(fail=fail)
    experts = {role: StageExpert(role.value, calls, control) for role in (
        ExpertType.DECODER, ExpertType.VERIFIER, ExpertType.ARBITER)}
    experts[ExpertType.SYNTHESIZER] = SynthesizerExpert(control.llm)
    orchestrator = Orchestrator(experts, page_cache_dir=tmp_path / "cache", page_cache_enabled=False,
                               monitor_enabled=False, fetch_concurrency=1)
    if fail:
        with pytest.raises(native.NativeRecoveryError, match="NATIVE_EXPERT_FAILED:synthesizer"):
            orchestrator.recheck_context(ctx, {}, control=control)
    else:
        assert orchestrator.recheck_context(ctx, {}, control=control) is ctx
    assert len(control.llm.prompts) == 1
    prompt = control.llm.prompts[0]
    assert "진단전용반례작품" not in prompt and "진단전용검색본문유일값" not in prompt
    assert "E901" not in prompt and "https://example.invalid/diagnostic" not in prompt
    assert "독립검색근거작품" in prompt and "독립검색본문유일값" in prompt and "E902" in prompt
    assert ctx.search_results is history and history == before
    assert history[0] is diagnostic and history[1] is ordinary
    if not fail:
        assert [role for role, _ in calls] == ["decoder", "verifier", "arbiter"]
        assert control.context_hashes[-1] == native._clone_and_digest(ctx)[1]


def test_normal_synthesizer_call_preserves_existing_search_input(tmp_path):
    from llm_batch.experts.synthesizer import SynthesizerExpert
    _, ctx = make_context()
    ctx.search_results = [{"title": "기존진단입력보존", "content": "기존경로본문",
        "url": "https://example.invalid/legacy", "_evidence_id": "E903", "_ocr_diagnostic_only": True}]
    llm = CapturingSynthesisLLM()
    orchestrator = Orchestrator({ExpertType.SYNTHESIZER: SynthesizerExpert(llm)},
        page_cache_dir=tmp_path / "cache", page_cache_enabled=False, monitor_enabled=False)
    result = orchestrator._call_expert(ExpertType.SYNTHESIZER, ctx, {})
    assert not result.get("error")
    assert "기존진단입력보존" in llm.prompts[0] and "기존경로본문" in llm.prompts[0]
    assert len(ctx.search_results) == 1


@pytest.mark.parametrize("field", ["context_sha256", "base_sha256", "upstream_sha256"])
@pytest.mark.parametrize("fault", ["missing", "wrong", "wrong_type"])
def test_continuation_rejects_fixed_control_binding_before_expert_or_io(tmp_path, monkeypatch, field, fault):
    import llm_batch.agentic_pipeline as module
    monkeypatch.setattr(module, "GatekeeperExpert", lambda llm: SimpleNamespace(llm=llm))
    capture = native.capture_pre_final(*make_context())
    bound = evidence(capture)
    control = control_case(capture, bound)
    if fault == "missing":
        control.binding.pop(field)
    elif fault == "wrong":
        control.binding[field] = "0" * 64
    else:
        control.binding[field] = 0
    pipe = AgenticPipeline(llm=control.llm, mcp=control.mcp, output_dir=tmp_path, native_recovery=True)
    monkeypatch.setattr(pipe.orchestrator, "recheck_context", lambda *a, **kw: pytest.fail("expert must not execute"))
    with pytest.raises(native.NativeRecoveryError, match="NATIVE_CONTROL_" + field.upper() + "_MISMATCH"):
        pipe.continue_native_recovery(capture, bound, control)
    assert not control.context_hashes and not control.llm.calls and not control.mcp.calls
    assert pipe.orchestrator._active_ctx is None and capture.verify_current()


@pytest.mark.parametrize("binding", [None, [], "missing_attribute"])
def test_continuation_requires_declared_fixed_control_binding(tmp_path, monkeypatch, binding):
    import llm_batch.agentic_pipeline as module
    monkeypatch.setattr(module, "GatekeeperExpert", lambda llm: SimpleNamespace(llm=llm))
    capture = native.capture_pre_final(*make_context())
    bound = evidence(capture)
    control = control_case(capture, bound)
    if binding == "missing_attribute":
        del control.binding
    else:
        control.binding = binding
    pipe = AgenticPipeline(llm=control.llm, mcp=control.mcp, output_dir=tmp_path, native_recovery=True)
    monkeypatch.setattr(pipe.orchestrator, "recheck_context", lambda *a, **kw: pytest.fail("expert must not execute"))
    with pytest.raises(native.NativeRecoveryError, match="NATIVE_CONTROL_BINDING_REQUIRED"):
        pipe.continue_native_recovery(capture, bound, control)
    assert not control.context_hashes and not control.llm.calls and not control.mcp.calls


def test_same_post_new_capture_cannot_reuse_old_control_binding(tmp_path, monkeypatch):
    import llm_batch.agentic_pipeline as module
    monkeypatch.setattr(module, "GatekeeperExpert", lambda llm: SimpleNamespace(llm=llm))
    post, ctx = make_context()
    old = native.capture_pre_final(post, ctx)
    ctx.expert_outputs["discourse"]["new_analysis"] = "같은 원문으로 새로 수행한 분석"
    current = native.capture_pre_final(post, ctx)
    assert current.source_snapshot == old.source_snapshot and current.context_sha256 != old.context_sha256
    bound = evidence(current)
    control = control_case(old, bound)
    # mutable 단계별 지문을 최신 값으로 바꾸어도 원장 최초 binding의 불일치를 숨길 수 없다.
    control.context_sha256 = current.context_sha256
    pipe = AgenticPipeline(llm=control.llm, mcp=control.mcp, output_dir=tmp_path, native_recovery=True)
    monkeypatch.setattr(pipe.orchestrator, "recheck_context", lambda *a, **kw: pytest.fail("expert must not execute"))
    with pytest.raises(native.NativeRecoveryError, match="NATIVE_CONTROL_CONTEXT_SHA256_MISMATCH"):
        pipe.continue_native_recovery(current, bound, control)
    assert not control.context_hashes and not control.llm.calls and not control.mcp.calls


def test_continuation_receipt_normalizes_tuple_spans_without_mutating_native_observation(tmp_path, monkeypatch):
    from copy import deepcopy
    from llm_batch.ledger.recovery_provider_journal import canonical_bytes as strict_json_bytes
    import llm_batch.agentic_pipeline as module
    monkeypatch.setattr(module, "GatekeeperExpert", lambda llm: SimpleNamespace(llm=llm))
    capture = native.capture_pre_final(*make_context())
    bound = evidence(capture)
    control = control_case(capture, bound)
    pipe = AgenticPipeline(llm=control.llm, mcp=control.mcp, output_dir=tmp_path, native_recovery=True)
    observation = {"origin_coordinates": [{"normalized_raw_span": (2, 9)}],
        "core_verdicts": [{"raw_span": (11, 23)}], "verified": True}
    before = deepcopy(observation)
    payload = {"identity": {"is_relevant": False}, "post_id": capture.post.post_id}
    output = SimpleNamespace(model_dump=lambda: deepcopy(payload))
    # 영수증 발행 경계만 격리한다. 실제 native guard의 positive/HOLD 증거는 workflow 묶음이 담당한다.
    def recheck(ctx, rules, *, control):
        ctx._native_recovery_expert_sequence = ["decoder", "verifier", "synthesizer", "arbiter"]
        return ctx
    def verify(current, serialized, *, stage):
        assert current is output and serialized == payload and stage == "recovery_native_continuation"
        return observation
    monkeypatch.setattr(pipe.orchestrator, "recheck_context", recheck)
    monkeypatch.setattr(pipe, "_context_to_output", lambda ctx: output)
    monkeypatch.setattr(pipe, "verify_final_source_context_serialization", verify)
    outcome = pipe.continue_native_recovery(capture, bound, control)
    receipt = outcome.receipt
    assert json.loads(strict_json_bytes(receipt)) == receipt
    assert receipt["native_serialization"] == {"origin_coordinates": [{"normalized_raw_span": [2, 9]}],
        "core_verdicts": [{"raw_span": [11, 23]}], "verified": True}
    assert native.canonical_bytes(observation) == strict_json_bytes(receipt["native_serialization"])
    assert receipt["receipt_sha256"] == hashlib.sha256(strict_json_bytes(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"})).hexdigest()
    assert observation == before and isinstance(observation["origin_coordinates"][0]["normalized_raw_span"], tuple)
    assert isinstance(observation["core_verdicts"][0]["raw_span"], tuple)
    assert outcome.output is output and output.model_dump() == payload and capture.verify_current()
    assert pipe.orchestrator._active_ctx is None
