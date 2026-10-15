"""같은 호출 context → main 부분 비용 → 완료 이벤트 전달을 검증한다.

process_post는 실제 메서드를 실행한다. 고정 context 시험에서는 전문가 응답과
무관한 출력/저장 경계만 대역으로 둔다. main은 실제 AST의 비용·이벤트 구간을
실행하며 전체 CLI나 모델 과금의 완전성을 주장하지 않는다.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

import expert_main
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.monitor.event_bus import MonitorState
from tests.test_candidate_retrieval_pipeline import _pipeline, _post, _public


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("토큰 연결 시험에서 외부 통신 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    for key in ("LLM_VLM_ENABLED", "PIPELINE_REASON_LLM_REVIEW", "PIPELINE_HERETIC_LIVE_FETCH",
                "PIPELINE_ACTIVE_LEARNING_QUEUE", "LLM_CONTEXT_COMPACT", "PIPELINE_POSTPROCESS_TRACE",
                "PIPELINE_CONTEXT_TO_OUTPUT_DUMP_AFTER"):
        monkeypatch.setenv(key, "0")


def context(post_id, prompt=17, completion=3):
    return SimpleNamespace(post_id=post_id, token_usage={"prompt_tokens": prompt,
        "completion_tokens": completion, "total_tokens": prompt + completion})


def shell(returned):
    """검증 대상 process_post는 그대로 두고 외부 expert와 비관련 기능을 OFF한다."""
    pipe = object.__new__(AgenticPipeline)
    pipe.worker_id, pipe.parallel_count = 1, 12
    pipe.orchestrator = SimpleNamespace(process=lambda **kwargs: returned)
    pipe.rules_config = {}
    pipe._use_session_knowledge = pipe.batch_context_learning_enabled = False
    for name in ("_observe_candidate_retrieval_shadow", "_observe_candidate_semantics",
                 "_observe_candidate_reranker_shadow", "_observe_candidate_inference", "_query_community_knowledge"):
        setattr(pipe, name, lambda *args, **kwargs: None)
    pipe._capture_final_source_original_inputs = lambda post: {"title": post.title}
    pipe._post_to_dict = lambda post: {"post_id": post.post_id, "title": post.title}
    pipe._extract_comments = lambda post: []
    pipe._maybe_enrich_post_images = lambda **kwargs: kwargs["post_dict"]
    pipe._context_to_output = lambda ctx: SimpleNamespace(status="SUCCESS", post_id=ctx.post_id)
    pipe._build_batch_context_learning_envelope = lambda ctx: None
    pipe._log_result = lambda *args: None
    pipe._append_active_learning_queue = lambda **kwargs: None
    pipe._error_output = lambda post_id, message: SimpleNamespace(status="ERROR", post_id=post_id)
    for name in ("_attach_community_knowledge", "_attach_candidate_semantics", "_attach_candidate_reranker_shadow",
                 "_attach_candidate_calibration_observations", "_attach_candidate_inference",
                 "_attach_candidate_retrieval_shadow"):
        setattr(pipe, name, lambda result, *args: result)
    return pipe


@pytest.fixture(scope="module")
def main_segments():
    tree = ast.parse((ROOT / "expert_main.py").read_text(encoding="utf-8-sig"))
    process = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_process_one")
    def assigned(node, name):
        return (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name
            or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets))
    start = next(i for i, n in enumerate(process.body) if assigned(n, "_ctx_token"))
    end = next(i for i, n in enumerate(process.body) if assigned(n, "_decision_cost_trace"))
    event = next(n for n in ast.walk(process) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "_monitor" and n.func.attr == "emit"
        and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "post_complete")
    serial = next(n for n in process.body if assigned(n, "result_dict"))
    search = next(n for n in ast.walk(process) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "_monitor" and n.func.attr == "emit"
        and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "search_stats")
    return process.body[start:end + 1], ast.Expr(value=deepcopy(event)), serial, ast.Expr(value=deepcopy(search))


def execute(nodes, namespace):
    module = ast.Module(body=deepcopy(nodes), type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(ROOT / "expert_main.py"), "exec"), namespace)


def main_usage(main_segments, pipe, post, *, monitor=None, index=1):
    """직접 복제한 계산식 대신 실제 main 비용·완료 이벤트 AST를 실행한다."""
    ns = dict(vars(expert_main))
    ns.update(pipeline=pipe, post=post, identity_dict={}, image_urls=[], publication_scope_id="a" * 64,
        ts="token-context-contract", index=index, worker_id=index, _post_elapsed=0.01,
        _post_started_at="2026-10-12T13:00:00+09:00", _post_finished_at="2026-10-12T13:00:01+09:00",
        _monitor=monitor or MonitorState(), _identity={}, _novel_id={}, result_dict={},
        content_texts=[], comment_texts=[])
    execute(main_segments[0], ns)
    execute([main_segments[1]], ns)
    return ns


def test_actual_orchestrator_noise_early_return_reaches_main(tmp_path, main_segments):
    pipe, llm, _ = _pipeline(tmp_path / "noise")
    llm.last_usage = {"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13}
    returned = []
    post = _post(11718092)
    result = pipe.process_post(post, native_context_sink=lambda p, ctx: returned.append(ctx))
    assert len(llm.calls) == 2  # 실제 Gatekeeper/Discourse 뒤 noise 조기 반환
    assert len(returned) == 1 and pipe.orchestrator._last_ctx is returned[0]
    assert returned[0].token_usage["total_tokens"] > 0
    _public(result)  # 에러 fallback을 성공 context로 오인하지 않음
    ns = main_usage(main_segments, pipe, post)
    assert ns["_ctx_token"] == returned[0].token_usage
    assert ns["_monitor"].get_status()["token_usage"] == returned[0].token_usage


def test_same_worker_normal_then_early_context_replaces_previous(main_segments):
    first, second = context(101, 50, 5), context(102, 7, 2)
    pipe = shell(first)
    assert pipe.process_post(_post(101)).status == "SUCCESS"
    assert pipe.orchestrator._last_ctx is first
    pipe.orchestrator.process = lambda **kwargs: second  # upstream이 _last_ctx를 쓰지 않는 반환
    observed = []
    result = pipe.process_post(_post(102), native_context_sink=lambda p, ctx: observed.append(ctx))
    assert result.status == "SUCCESS" and observed == [second]
    assert pipe.orchestrator._last_ctx is second
    ns = main_usage(main_segments, pipe, _post(102))
    assert ns["_decision_cost_trace"].total_tokens == 9
    assert ns["_monitor"].get_status()["token_usage"]["total_tokens"] == 9


@pytest.mark.parametrize("failure_stage", ["pre_observation", "orchestrator", "none_return"])
def test_same_id_failed_retry_never_reuses_prior_attempt(failure_stage, main_segments):
    pipe = shell(context(101))
    pipe.process_post(_post(101))
    def fail(*args, **kwargs):
        raise RuntimeError("fixed failure")
    if failure_stage == "pre_observation":
        pipe._observe_candidate_retrieval_shadow = fail
        with pytest.raises(RuntimeError, match="fixed failure"):
            pipe.process_post(_post(101))
    else:
        pipe.orchestrator.process = fail if failure_stage == "orchestrator" else lambda **kwargs: None
        assert pipe.process_post(_post(101)).status == "ERROR"
    assert getattr(pipe.orchestrator, "_last_ctx", None) is None
    ns = main_usage(main_segments, pipe, _post(101))
    assert ns["_ctx_token"] == {}
    assert ns["_decision_cost_trace"].total_tokens is None


def test_error_after_context_keeps_only_same_row_partial_usage(main_segments):
    ctx = context(102, 30, 4)
    pipe = shell(ctx)
    pipe.orchestrator._last_ctx = context(101, 999, 999)
    def fail(ctx):
        raise RuntimeError("conversion failure")
    pipe._context_to_output = fail
    assert pipe.process_post(_post(102)).status == "ERROR"
    assert pipe.orchestrator._last_ctx is ctx
    ns = main_usage(main_segments, pipe, _post(102))
    assert ns["_decision_cost_trace"].total_tokens == 34
    assert ns["_decision_cost_trace"].expert_calls is None
    assert not ns["_decision_cost_trace"].action_applied


@pytest.mark.parametrize("signal", [SystemExit, KeyboardInterrupt])
def test_shutdown_before_return_does_not_retain_old_context(signal):
    pipe = shell(None)
    pipe.orchestrator._last_ctx = context(101)
    def stop(**kwargs):
        raise signal()
    pipe.orchestrator.process = stop
    with pytest.raises(signal):
        pipe.process_post(_post(102))
    assert not hasattr(pipe.orchestrator, "_last_ctx")


@pytest.mark.parametrize("context_id", [102, "101", True, None])
def test_main_rejects_other_or_untyped_post_context(context_id, main_segments):
    post = _post(1 if context_id is True else 101)
    ns = main_usage(main_segments, shell_with_last(context(context_id)), post)
    assert ns["_ctx_token"] == {}
    assert ns["_decision_cost_trace"].total_tokens is None


def shell_with_last(ctx):
    return SimpleNamespace(orchestrator=SimpleNamespace(_last_ctx=ctx))


@pytest.mark.parametrize("tokens", [None, {}, {"prompt_tokens": True, "completion_tokens": 1},
    {"prompt_tokens": -1, "completion_tokens": 1}, {"prompt_tokens": 1, "completion_tokens": None}])
def test_main_preserves_unknown_instead_of_creating_zero(tokens, main_segments):
    ctx = SimpleNamespace(post_id=101, token_usage=tokens)
    ns = main_usage(main_segments, shell_with_last(ctx), _post(101))
    assert ns["_ctx_token"] == {}
    assert ns["_decision_cost_trace"].prompt_tokens is None
    assert ns["_decision_cost_trace"].completion_tokens is None
    assert ns["_decision_cost_trace"].total_tokens is None


def test_known_zero_remains_known_zero_and_total_is_recomputed(main_segments):
    ctx = context(101, 0, 0)
    ctx.token_usage["total_tokens"] = 999  # 기존 main 계약은 prompt+completion을 사용
    ns = main_usage(main_segments, shell_with_last(ctx), _post(101))
    assert ns["_ctx_token"]["total_tokens"] == 0
    assert ns["_decision_cost_trace"].total_tokens == 0


def test_parallel_completed_usage_reaches_monitor_before_batch_end(main_segments):
    monitor = MonitorState()
    monitor.emit("batch_start", {"total": 12, "parallel_count": 12})
    rows = [(11718092, 18654, 655), (8620907, 20558, 882), (8362499, 23980, 739)]
    for index, (pid, prompt, completion) in enumerate(rows, 1):
        ns = main_usage(main_segments, shell_with_last(context(pid, prompt, completion)),
                        _post(pid), monitor=monitor, index=index)
        assert ns["_decision_cost_trace"].total_tokens == prompt + completion
    status = monitor.get_status()
    assert status["batch_running"] and status["done_count"] == 3
    assert status["token_usage"] == {"prompt_tokens": 63192, "completion_tokens": 2276, "total_tokens": 65468}
    main_usage(main_segments, shell_with_last(context(8362499, 23980, 739)), _post(8362499), monitor=monitor)
    assert monitor.get_status()["token_usage"] == status["token_usage"]  # duplicate 완료 무시
    restored = MonitorState()
    restored.load_status_snapshot(status)
    assert restored.get_status()["token_usage"] == status["token_usage"]


def test_no_output_serialization_stops_before_usage_and_completion(main_segments):
    monitor = MonitorState()
    ns = {"result": None, "_monitor": monitor}
    with pytest.raises(TypeError):
        execute([main_segments[2], *main_segments[0], main_segments[1]], ns)
    assert "_ctx_token" not in ns
    assert monitor.get_status()["done_count"] == 0


def test_main_search_stats_tags_worker_without_changing_cumulative_counts(main_segments):
    events = []
    ns = {"pipeline": SimpleNamespace(_search_cache_hits=20, _search_cache_misses=96),
          "worker_id": 7, "_monitor": SimpleNamespace(emit=lambda *args: events.append(args))}
    execute([main_segments[3]], ns)
    assert events == [("search_stats", {"hits": 20, "misses": 96, "worker_id": 7})]
