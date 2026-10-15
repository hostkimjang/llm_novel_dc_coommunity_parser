from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
from unittest.mock import patch

import pytest

from llm_batch import agentic_pipeline as pipeline_module
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import CommentInput, ContentBlock, PostInput
from llm_batch.experts.orchestrator import ExpertType


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class FakeLLM:
    last_usage = None

    def __init__(self):
        self.calls = []

    def complete_json(self, role, post, comments):
        self.calls.append((role, deepcopy(post), deepcopy(comments)))
        if role == "gatekeeper":
            return {"is_noise": True, "noise_reason": "일상적인 음식 이야기", "post_type": "noise", "detected_entities": {}, "search_requests": []}
        return {"discourse_analysis": {"primary_domain": "real_world", "domain_confidence": "high", "intent": "chat"}}


class FakeMCP:
    def __init__(self):
        self.calls = []

    def search(self, query, purpose=""):
        self.calls.append((query, purpose))
        return {"results": [{"title": "일상", "url": "https://example.invalid/source", "content": "일상 이야기"}], "total": 1, "raw_total": 1, "retry_count": 0}


class FakeExpert:
    def __init__(self, llm, role, search=None):
        self.llm, self.role, self.search = llm, role, search

    def analyze(self, post, comments, *args, **kwargs):
        if self.search:
            self.search("기존 전문가 검색", "verify")
        return self.llm.complete_json(self.role, post, comments)


class RecordingObserver:
    def __init__(self):
        self.views = []
        self.returned = []
        self.lock = threading.Lock()

    def observe(self, view):
        receipt = {"schema_version": "candidate_retrieval_shadow_v1", "mode": "SHADOW", "status": "OK",
            "post_id": view["post_id"], "query_sha256": _digest(view), "publication_authority": False, "public_apply": False, "central_db_write": False, "latency_ms": 0.0,
            "reason_codes": [], "ranked_candidates": [{"corpus_candidate_id": "unpublished-shadow-only", "title": "공개되면 안 되는 후보"}]}
        with self.lock:
            self.views.append(deepcopy(view))
            self.returned.append(receipt)
        return receipt


@pytest.fixture(autouse=True)
def no_external_or_extra_runtime(monkeypatch):
    monkeypatch.setenv("LLM_VLM_ENABLED", "0")
    monkeypatch.setenv("PIPELINE_REASON_LLM_REVIEW", "0")
    monkeypatch.setenv("PIPELINE_HERETIC_LIVE_FETCH", "0")
    monkeypatch.setenv("PIPELINE_ACTIVE_LEARNING_QUEUE", "0")
    monkeypatch.setenv("LLM_CONTEXT_COMPACT", "0")
    monkeypatch.setenv("PIPELINE_POSTPROCESS_TRACE", "0")
    monkeypatch.setenv("PIPELINE_CONTEXT_TO_OUTPUT_DUMP_AFTER", "0")
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: pytest.fail("network is forbidden"))


def _pipeline(tmp_path, observer=None):
    llm, mcp = FakeLLM(), FakeMCP()
    # Kiwi 등의 실제 expert 초기화만 대역으로 바꾸며 process/orchestrator/output 경로는 실행한다.
    with patch.object(pipeline_module, "GatekeeperExpert", lambda client: FakeExpert(client, "gatekeeper")):
        pipeline = AgenticPipeline(llm=llm, mcp=mcp, output_dir=tmp_path, parallel_count=2, candidate_retrieval_shadow=observer)
    pipeline.experts = {
        ExpertType.GATEKEEPER: FakeExpert(llm, "gatekeeper", pipeline._search),
        ExpertType.DISCOURSE: FakeExpert(llm, "discourse"),
    }
    pipeline.orchestrator.experts = pipeline.experts
    # 이 묶음은 실제 fake expert 경로를 비교한다. fast-path 자체는 별도 시험에서 실행한다.
    pipeline.orchestrator._try_fast_path = lambda *a, **kw: None
    return pipeline, llm, mcp


def _post(post_id=901):
    return PostInput(post_id=post_id, title="오늘 저녁에 무엇을 먹을까", content_blocks=[ContentBlock(type="text", text="따뜻한 음식을 먹고 싶다")],
        comments=[{"comment_id": "c1", "content": "나는 국수를 먹었다"}],
        judge_seed={"official_title": "REFERENCE_MUST_NOT_REACH_QUERY"},
        search_results=[{"title": "SEARCH_MUST_NOT_REACH_QUERY"}])


def _public(result):
    value = result.model_dump(mode="json")
    assert not str(value["identity"].get("reason", "")).startswith("처리 오류:")
    assert "_candidate_retrieval_shadow" not in value
    return value


def test_actual_process_post_shadow_preserves_expert_search_and_public_result(tmp_path):
    off, off_llm, off_mcp = _pipeline(tmp_path / "off")
    observer = RecordingObserver()
    shadow, shadow_llm, shadow_mcp = _pipeline(tmp_path / "shadow", observer)
    source = _post()
    before = source.model_dump()
    baseline = off.process_post(source)
    observed = shadow.process_post(source)
    assert _public(baseline) == _public(observed)
    assert off_llm.calls == shadow_llm.calls and len(off_llm.calls) == 2
    assert off_mcp.calls == shadow_mcp.calls and len(off_mcp.calls) == 1
    assert len(observer.views) == 1
    assert source.model_dump() == before
    assert "_candidate_retrieval_shadow" not in baseline.__dict__
    receipt = observed.__dict__["_candidate_retrieval_shadow"]
    assert receipt == observer.returned[0] and receipt is not observer.returned[0]
    assert receipt["post_id"] == source.post_id and receipt["query_sha256"] == _digest(observer.views[0])
    assert "unpublished-shadow-only" not in json.dumps(_public(observed), ensure_ascii=False)
    assert "REFERENCE_MUST_NOT_REACH_QUERY" not in json.dumps(observer.views)
    assert "SEARCH_MUST_NOT_REACH_QUERY" not in json.dumps(observer.views)


def test_source_paths_and_untrimmed_comments_survive_actual_entry(tmp_path):
    observer = RecordingObserver()
    pipeline, _, _ = _pipeline(tmp_path, observer)
    post = _post()
    post.content_blocks = [ContentBlock(type="image", url="https://example.invalid/pixel"), ContentBlock(type="text", text="  원문 그대로  ")]
    post.comments = [{"content": f"댓글 {i}"} for i in range(16)] + ["문자열 댓글", {"text": "text 키"}, CommentInput(comment_id="typed", post_id=901, content="typed 댓글")]
    result = pipeline.process_post(post)
    _public(result)
    fragments = observer.views[0]["fragments"]
    assert {"raw_path": "/content_blocks/1/text", "kind": "BODY", "text": "  원문 그대로  "} in fragments
    assert {"raw_path": "/comments/15/content", "kind": "COMMENT", "text": "댓글 15"} in fragments
    assert {"raw_path": "/comments/16", "kind": "COMMENT", "text": "문자열 댓글"} in fragments
    assert {"raw_path": "/comments/17/text", "kind": "COMMENT", "text": "text 키"} in fragments
    assert {"raw_path": "/comments/18/content", "kind": "COMMENT", "text": "typed 댓글"} in fragments
    assert not any("pixel" in x["text"] for x in fragments)


@pytest.mark.parametrize("behavior,code", [("raise", "OBSERVER_EXCEPTION"), ("invalid", "INVALID_RECEIPT"), ("oversize", "RECEIPT_LIMIT_EXCEEDED"), ("wrong_post", "INVALID_RECEIPT"), ("wrong_query", "QUERY_FINGERPRINT_MISMATCH"), ("authority", "INVALID_RECEIPT")])
def test_observer_failure_preserves_actual_public_result_and_records_error(tmp_path, behavior, code):
    class Broken(RecordingObserver):
        def observe(self, view):
            value = super().observe(view)
            if behavior == "raise":
                raise RuntimeError("SECRET_EXCEPTION_MUST_NOT_BE_STORED")
            if behavior == "invalid":
                return {"not_json": object()}
            if behavior == "oversize":
                value["too_large"] = "가" * 65536
            if behavior == "wrong_post":
                value["post_id"] = "other"
            if behavior == "wrong_query":
                value["query_sha256"] = "a"*64
            if behavior == "authority":
                value["public_apply"] = True
            return value
    baseline, _, _ = _pipeline(tmp_path / "off")
    observer = Broken()
    pipeline, _, _ = _pipeline(tmp_path / "shadow", observer)
    expected = baseline.process_post(_post())
    output = pipeline.process_post(_post())
    assert _public(output) == _public(expected) and len(observer.views) == 1
    receipt = output.__dict__["_candidate_retrieval_shadow"]
    assert receipt["status"] == "ERROR" and receipt["reason_codes"] == [code]
    assert receipt["query_sha256"] == _digest(observer.views[0])
    assert "SECRET_EXCEPTION" not in json.dumps(receipt)


def test_mutating_observer_and_reused_receipt_cannot_modify_sources_or_prior_output(tmp_path):
    class Reusing(RecordingObserver):
        def __init__(self):
            super().__init__()
            self.shared = {}

        def observe(self, view):
            self.shared.clear()
            self.shared.update(super().observe(view))
            view["fragments"][0]["text"] = "observer mutation"
            return self.shared
    observer = Reusing()
    pipeline, _, _ = _pipeline(tmp_path, observer)
    first_source, second_source = _post(901), _post(902)
    first = pipeline.process_post(first_source)
    first_receipt = deepcopy(first.__dict__["_candidate_retrieval_shadow"])
    second = pipeline.process_post(second_source)
    assert first.__dict__["_candidate_retrieval_shadow"] == first_receipt
    assert second.__dict__["_candidate_retrieval_shadow"]["post_id"] == 902
    assert first_source.title == second_source.title == "오늘 저녁에 무엇을 먹을까"


def test_error_output_and_off_reuse_do_not_lose_or_leak_private_receipt(tmp_path):
    observer = RecordingObserver()
    pipeline, _, _ = _pipeline(tmp_path, observer)
    with patch.object(pipeline.orchestrator, "process", side_effect=RuntimeError("expert failure")):
        result = pipeline.process_post(_post())
    assert result.identity.reason.startswith("처리 오류:")
    assert result.__dict__["_candidate_retrieval_shadow"]["post_id"] == 901
    assert len(observer.views) == 1
    pipeline._candidate_retrieval_shadow = None
    with patch.object(pipeline, "_context_to_output", return_value=result):
        reused = pipeline.process_post(_post())
    assert reused is result and "_candidate_retrieval_shadow" not in reused.__dict__
    assert len(observer.views) == 1


def test_shared_observer_query_and_receipt_are_isolated_across_actual_workers(tmp_path):
    observer = RecordingObserver()
    workers = [_pipeline(tmp_path / str(i), observer)[0] for i in range(2)]
    posts = [_post(911), _post(912)]
    posts[0].title, posts[1].title = "첫 번째 사람의 저녁", "두 번째 사람의 아침"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(lambda pair: pair[0].process_post(pair[1]), zip(workers, posts)))
    assert len(observer.views) == 2
    views = {view["post_id"]: view for view in observer.views}
    for output, post in zip(outputs, posts):
        _public(output)
        receipt = output.__dict__["_candidate_retrieval_shadow"]
        assert receipt["post_id"] == post.post_id and receipt["query_sha256"] == _digest(views[post.post_id])
        assert views[post.post_id]["fragments"][0]["text"] == post.title


def test_fast_path_still_observes_exactly_once_without_expert_or_search_calls(tmp_path):
    observer = RecordingObserver()
    pipeline, llm, mcp = _pipeline(tmp_path, observer)
    del pipeline.orchestrator._try_fast_path
    output = pipeline.process_post(PostInput(post_id=920, title=""))
    _public(output)
    assert len(observer.views) == 1 and not llm.calls and not mcp.calls


def _real_observer(tmp_path):
    from llm_batch.grounding.candidate_retrieval_shadow import candidate_content_sha256, load_candidate_retrieval_shadow
    entry = {"corpus_candidate_id": "fixture-meal", "work_id": "work-meal", "edition_id": "edition-text", "media_type": "NOVEL",
        "title": "따뜻한 음식", "aliases": [], "text": "국수 저녁 음식",
        "content_sha256": candidate_content_sha256("따뜻한 음식", [], "국수 저녁 음식"),
        "sources": [{"source_ref": "synthetic://meal-fixture", "source_sha256": "1"*64, "lineage_id": "fixture-lineage",
            "observed_at": "2026-10-10T00:00:00+09:00", "rights": {"status": "SYNTHETIC_FIXTURE", "basis": "새로 작성한 시험 문구"}}]}
    corpus = {"schema_version": "frozen_candidate_corpus_v1", "corpus_id": "pipeline-fixture", "data_kind": "SYNTHETIC_FIXTURE", "entries": [entry]}
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    return load_candidate_retrieval_shadow(path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_actual_bm25_adapter_observes_actual_pipeline_without_publication(tmp_path):
    from llm_batch.ledger.publication_commit import _stable_result_payload
    from llm_batch.runtime.candidate_retrieval import export_candidate_retrieval_fields
    real = _real_observer(tmp_path)
    class Counted:
        def __init__(self):
            self.calls = 0
        def observe(self, view):
            self.calls += 1
            return real.observe(view)
    observer = Counted()
    off, off_llm, off_mcp = _pipeline(tmp_path / "off")
    pipeline, llm, mcp = _pipeline(tmp_path / "shadow", observer)
    expected = off.process_post(_post())
    output = pipeline.process_post(_post())
    assert _public(output) == _public(expected) and llm.calls == off_llm.calls and mcp.calls == off_mcp.calls
    receipt = output.__dict__["_candidate_retrieval_shadow"]
    assert observer.calls == 1 and receipt["status"] == "OK"
    assert receipt["ranked_candidates"][0]["corpus_candidate_id"] == "fixture-meal"
    assert receipt["central_db_write"] is False and receipt["latency_ms"] >= 0
    assert receipt["source_fragments"][0]["raw_path"] == "/title"
    assert "fixture-meal" not in json.dumps(_public(output), ensure_ascii=False)
    assert receipt["ranked_candidates"][0]["source_refs"]
    binding = {"run_id": "synthetic-pipeline-test", "input_index": 1, "post_id": 901, "attempt_id": "fixture-attempt", "publication_scope_id": "fixture-scope"}
    stored = export_candidate_retrieval_fields(output, real, binding=binding)
    saved_receipt = stored["candidate_retrieval_shadow"]
    assert saved_receipt["status"] == "OK"
    assert saved_receipt["binding"]["input_index"] == 1 and saved_receipt["binding"]["scope"] == "ATTEMPT_LOCAL_OBSERVATION"
    assert saved_receipt["ranked_candidates"] == receipt["ranked_candidates"]
    assert saved_receipt["latency_ms"] == receipt["latency_ms"]
    assert saved_receipt["observation_sha256"] == receipt["observation_sha256"]
    before = {"post_id": 901, "analysis_result": _public(expected), "run_meta": {"run_id": binding["run_id"]}}
    after = {"post_id": 901, "analysis_result": _public(output), "run_meta": {"run_id": binding["run_id"], **stored}}
    assert _stable_result_payload(before) == _stable_result_payload(after)


def test_real_adapter_query_limit_retains_reason_and_original_query_fingerprint(tmp_path):
    real = _real_observer(tmp_path)
    observer = RecordingObserver()
    def observe(view):
        observer.views.append(deepcopy(view))
        return real.observe(view)
    observer.observe = observe
    off, _, _ = _pipeline(tmp_path / "off")
    pipeline, _, _ = _pipeline(tmp_path / "shadow", observer)
    source = _post()
    source.content_blocks = [ContentBlock(type="text", text="가"*12001)]
    expected, output = off.process_post(source), pipeline.process_post(source)
    assert _public(output) == _public(expected) and len(observer.views) == 1
    receipt = output.__dict__["_candidate_retrieval_shadow"]
    assert receipt["status"] == "QUERY_LIMIT_EXCEEDED" and "QUERY_CHAR_LIMIT" in receipt["reason_codes"]
    assert receipt["query_sha256"] == _digest(observer.views[0]) and receipt["post_id"] == source.post_id
    assert receipt["adapter_observation_sha256"] and receipt["adapter_observation_sha256"] != receipt["observation_sha256"]
    assert receipt["observation_sha256"] == _digest({key: value for key, value in receipt.items() if key not in {"latency_ms", "observation_sha256"}})


def test_query_capture_encoding_failure_does_not_change_actual_processing(tmp_path):
    observer = RecordingObserver()
    off, _, _ = _pipeline(tmp_path / "off")
    pipeline, _, _ = _pipeline(tmp_path / "shadow", observer)
    expected = off.process_post(_post())
    dumps = json.dumps
    def fail_source_view(value, *args, **kwargs):
        if isinstance(value, dict) and value.get("schema_version") == "candidate_retrieval_source_view_v1":
            raise UnicodeError("invalid source encoding")
        return dumps(value, *args, **kwargs)
    with patch.object(pipeline_module.json, "dumps", side_effect=fail_source_view):
        output = pipeline.process_post(_post())
    assert _public(output) == _public(expected)
    assert not observer.views
    receipt = output.__dict__["_candidate_retrieval_shadow"]
    assert receipt["status"] == "ERROR" and receipt["reason_codes"] == ["SOURCE_VIEW_CAPTURE_FAILED"]
    assert receipt["query_sha256"] is None and receipt["query_sha256_basis"] == "NOT_AVAILABLE_CAPTURE_FAILED"
