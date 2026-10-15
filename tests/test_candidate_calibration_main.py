"""선택 전 capture·명시 FROZEN 교정의 실제 pipeline 및 main 저장 연결 회귀.

외부 전문가/검색은 대역으로 두되 process_post, 관측, exporter와 공개 WAL
projection은 실제 함수를 실행한다. 새 자료의 정답이나 운영 품질을 추정하지 않는다.
"""
import ast
import builtins
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import patch

import pytest

from llm_batch import agentic_pipeline as pipeline_module
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ExpertType
from llm_batch.ledger.publication_commit import _stable_result_payload
from llm_batch.runtime import candidate_calibration as calibration
from llm_batch.runtime import candidate_capture as capture_storage
from llm_batch.runtime import candidate_reranker as reranker
from llm_batch.runtime.execution_config import source_snapshot
from test_candidate_retrieval_pipeline import FakeLLM, FakeMCP, FakeExpert, _post, _public, no_external_or_extra_runtime
from test_candidate_reranker_runtime import setup_scorer, setup_retrieval

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "expert_main.py"
INPUT_SHA = "a" * 64


@pytest.fixture(scope="module")
def main_tree():
    return ast.parse(MAIN.read_text(encoding="utf-8-sig"))


@pytest.fixture(scope="module")
def frozen_bundle(tmp_path_factory):
    from tests.candidate_calibration_runtime_fixtures import build_runtime_calibration_fixture
    value = build_runtime_calibration_fixture(tmp_path_factory.mktemp("main_frozen_calibration"))
    value["observer"] = calibration.prepare_candidate_calibration(value["settings"], value["scorer"])
    assert value["observer"].summary()["status"] == "AVAILABLE"
    return value


def _pipeline(path, retrieval, scorer, observer=None):
    llm, mcp = FakeLLM(), FakeMCP()
    with patch.object(pipeline_module, "GatekeeperExpert", lambda client: FakeExpert(client, "gatekeeper")):
        pipe = AgenticPipeline(llm=llm, mcp=mcp, output_dir=path, parallel_count=1,
            candidate_retrieval_shadow=retrieval, candidate_reranker_shadow=scorer,
            candidate_calibration=observer)
    pipe.experts = {ExpertType.GATEKEEPER: FakeExpert(llm, "gatekeeper", pipe._search),
                    ExpertType.DISCOURSE: FakeExpert(llm, "discourse")}
    pipe.orchestrator.experts = pipe.experts
    pipe.orchestrator._try_fast_path = lambda *args, **kwargs: None
    return pipe, llm, mcp


def _row_exporter(tree, path, scorer, observer, *, semantic=None, retrieval=None):
    """외부 실행 없이 main의 실제 closure 본문을 동일 입력으로 호출한다."""
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name == "_candidate_calibration_row_fields")
    namespace = {"Any": Any, "Dict": Dict, "_candidate_calibration": observer,
        "_candidate_reranker": scorer, "ts": "calibration-main-run", "publication_scope_id": "main-scope",
        "_decision_call_row_attempt_id": lambda index, post_id: f"attempt-{index}-{post_id}",
        "OUT_DIR": path, "_input_snapshot_sha256": INPUT_SHA,
        "_candidate_semantics": semantic, "_candidate_retrieval_observer": retrieval,
        "export_candidate_calibration_fields": calibration.export_candidate_calibration_fields}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(MAIN), "exec"), namespace)
    def invoke(result, index, post):
        # 구형 시험의 post_id 인수도 그대로인 typed ID로 전달한다.
        if node.args.args[-1].arg == "post":
            post = post if hasattr(post, "post_id") else SimpleNamespace(post_id=post)
        elif hasattr(post, "post_id"):
            post = post.post_id
        return namespace[node.name](result, index, post)
    return invoke


def test_main_semantic_model_saves_real_capture_when_calibration_is_off(tmp_path, main_tree):
    from test_candidate_reranker_runtime import semantic_observed
    scorer, state, package, value = semantic_observed(tmp_path)
    result = SimpleNamespace(_candidate_reranker_shadow=value["receipt"],
        _candidate_reranker_capture=value["capture"], _candidate_reranker_semantics=package)
    output = tmp_path / "main-semantic"
    fields = _row_exporter(main_tree, output, scorer, None, semantic=state["observer"],
        retrieval=state["retrieval"])(result, 4, state["post"])
    assert set(fields) == {"candidate_reranker_capture"}
    ref = fields["candidate_reranker_capture"]
    assert ref["status"] == "SAVED" and ref["schema_version"] == "candidate_reranker_capture_ref_v2", ref
    saved = json.loads((output / ref["artifact"]["path"]).read_bytes())
    assert saved["observation"] == value["capture"]
    assert saved["binding"]["post_id"] == state["post"].post_id and saved["binding"]["input_index"] == 4
    assert saved["input_snapshot_sha256"] == INPUT_SHA


def _startup_calibration(tree, args, environment):
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    body, collecting = [], False
    for node in main.body:
        assigned = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        if "_candidate_calibration_settings" in assigned:
            collecting = True
        if collecting:
            body.append(node)
        if "_candidate_calibration" in assigned:
            break
    marker = object()
    namespace = {"_CLI_ARGS": args, "os": SimpleNamespace(environ=environment),
        "_candidate_reranker": object(),
        "resolve_candidate_calibration_settings": calibration.resolve_candidate_calibration_settings,
        "prepare_candidate_calibration": lambda settings, scorer: marker if settings["mode"] == "SHADOW" else None}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(MAIN), "exec"), namespace)
    return namespace["_candidate_calibration_settings"], namespace["_candidate_calibration"]


def test_main_cli_resolution_precedence_and_default_off(main_tree):
    import expert_main
    args = expert_main._parse_args([])
    settings, observer = _startup_calibration(main_tree, args, {})
    assert settings["mode"] == "OFF" and observer is None
    args = expert_main._parse_args(["--candidate-calibration", "OFF"])
    settings, observer = _startup_calibration(main_tree, args,
        {"EXPERT_CANDIDATE_CALIBRATION": "SHADOW", "EXPERT_CALIBRATION_BUNDLE": "env.json",
         "EXPERT_CALIBRATION_BUNDLE_SHA256": "b" * 64})
    assert settings["mode"] == "OFF" and settings["sources"]["mode"] == "CLI" and observer is None
    args = expert_main._parse_args(["--candidate-retrieval", "SHADOW", "--candidate-reranker", "SHADOW",
        "--candidate-calibration", "SHADOW", "--calibration-bundle", "cli.json", "--calibration-bundle-sha256", "c" * 64])
    settings, observer = _startup_calibration(main_tree, args, {})
    assert settings["bundle_path"] == "cli.json" and settings["bundle_sha256"] == "c" * 64 and observer is not None


@pytest.mark.parametrize("retrieval_mode,reranker_mode", [("OFF", "OFF"), ("OFF", "SHADOW"), ("SHADOW", "OFF")])
def test_main_rejects_missing_explicit_shadow_dependencies(main_tree, retrieval_mode, reranker_mode):
    import expert_main
    args = expert_main._parse_args(["--candidate-retrieval", retrieval_mode, "--candidate-reranker", reranker_mode,
        "--candidate-calibration", "SHADOW", "--calibration-bundle", "x.json", "--calibration-bundle-sha256", "d" * 64])
    with pytest.raises(ValueError, match="RETRIEVAL_AND_RERANKER_SHADOW_REQUIRED"):
        _startup_calibration(main_tree, args, {})


def test_off_process_keeps_legacy_four_argument_call_and_no_capture_import(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    pipe, llm, mcp = _pipeline(tmp_path / "off", retrieval, scorer)
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        assert not name.endswith(("candidate_calibration", "candidate_capture", "candidate_reranker_capture"))
        return original_import(name, *args, **kwargs)
    with patch.object(reranker, "observe_candidate_reranker", wraps=reranker.observe_candidate_reranker) as legacy, \
         patch.object(reranker, "observe_candidate_reranker_with_capture", side_effect=AssertionError("OFF capture")), \
         patch.object(builtins, "__import__", guarded_import):
        result = pipe.process_post(_post())
    _public(result)
    assert len(legacy.call_args.args) == 4 and legacy.call_count == 1
    assert len(llm.calls) == 2 and len(mcp.calls) == 1
    assert "_candidate_reranker_capture" not in result.__dict__ and "_candidate_calibration_shadow" not in result.__dict__


def test_on_process_uses_one_preselection_score_and_preserves_public_calls(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    off, off_llm, off_mcp = _pipeline(tmp_path / "off", retrieval, scorer)
    on, on_llm, on_mcp = _pipeline(tmp_path / "on", retrieval, scorer, object())
    post = _post(); before = post.model_dump()
    baseline = off.process_post(post)
    original_score = type(scorer).score; calls = []
    def scored(self, view):
        assert not on_llm.calls and not on_mcp.calls
        calls.append(deepcopy(view)); return original_score(self, view)
    def consume(observer, source, capture, raw):
        assert not on_llm.calls and not on_mcp.calls
        assert capture["frozen_view"] == calls[0] and capture["raw_receipt"] == raw
        return {"post_id": source.post_id, "status": "NOT_AVAILABLE", "reason_codes": ["FROZEN_ROW_NOT_ASSIGNED"]}
    with patch.object(type(scorer), "score", scored), patch.object(calibration, "observe_candidate_calibration", consume):
        result = on.process_post(post)
    assert len(calls) == 1 and _public(result) == _public(baseline)
    assert off_llm.calls == on_llm.calls and off_mcp.calls == on_mcp.calls and post.model_dump() == before
    assert result._candidate_reranker_capture["raw_receipt"] == result._candidate_reranker_shadow
    assert result._candidate_calibration_shadow["post_id"] == post.post_id
    assert all(not key.startswith("_candidate_") for key in result.model_dump())


def test_consumer_exception_keeps_obtained_capture_and_original_analysis(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    off, _, _ = _pipeline(tmp_path / "off", retrieval, scorer)
    on, _, _ = _pipeline(tmp_path / "on", retrieval, scorer, object())
    baseline = off.process_post(_post())
    with patch.object(calibration, "observe_candidate_calibration", side_effect=RuntimeError("PRIVATE_MODEL_SECRET")):
        result = on.process_post(_post())
    assert _public(result) == _public(baseline)
    assert result._candidate_reranker_capture["raw_receipt"] == result._candidate_reranker_shadow
    assert "_candidate_calibration_shadow" not in result.__dict__
    assert "PRIVATE_MODEL_SECRET" not in json.dumps(result.model_dump(mode="json"), ensure_ascii=False)


def test_expert_error_preserves_all_three_current_observations(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    pipe, _, _ = _pipeline(tmp_path / "error", retrieval, scorer, object())
    with patch.object(calibration, "observe_candidate_calibration", return_value={"post_id": 901, "status": "NOT_AVAILABLE"}), \
         patch.object(pipe.orchestrator, "process", side_effect=RuntimeError("synthetic expert failure")):
        result = pipe.process_post(_post())
    assert "처리 오류:" in result.identity.reason
    assert result._candidate_reranker_shadow["post_id"] == 901
    assert result._candidate_reranker_capture["post_id"] == 901
    assert result._candidate_calibration_shadow["post_id"] == 901


def test_reused_result_clears_old_private_capture_when_calibration_is_off(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    pipe, _, _ = _pipeline(tmp_path / "reuse", retrieval, scorer, object())
    with patch.object(calibration, "observe_candidate_calibration", return_value={"post_id": 901}):
        old_result = pipe.process_post(_post())
    assert "_candidate_reranker_capture" in old_result.__dict__
    pipe._candidate_calibration = None
    with patch.object(pipe.orchestrator, "process", side_effect=RuntimeError("synthetic reuse")), \
         patch.object(pipe, "_error_output", return_value=old_result):
        reused = pipe.process_post(_post(902))
    assert reused is old_result and reused._candidate_reranker_shadow["post_id"] == 902
    assert "_candidate_reranker_capture" not in reused.__dict__ and "_candidate_calibration_shadow" not in reused.__dict__


def test_shared_observers_keep_separate_worker_calls_isolated(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    shared = object()
    workers = [_pipeline(tmp_path / str(i), retrieval, scorer, shared)[0] for i in range(2)]
    def consume(observer, post, capture, receipt):
        assert observer is shared and capture["post_id"] == receipt["post_id"] == post.post_id
        return {"post_id": post.post_id}
    with patch.object(calibration, "observe_candidate_calibration", consume), ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: pair[0].process_post(_post(pair[1])), zip(workers, [903, 904])))
    assert [r._candidate_reranker_capture["post_id"] for r in results] == [903, 904]
    assert [r._candidate_calibration_shadow["post_id"] for r in results] == [903, 904]
    assert results[0]._candidate_reranker_capture is not results[1]._candidate_reranker_capture


def test_real_frozen_pipeline_main_capture_storage_and_public_wal_invariance(tmp_path, main_tree, frozen_bundle):
    data = frozen_bundle
    row = data["frozen_runtime_rows"][0]; post = row["post"]
    off, off_llm, off_mcp = _pipeline(tmp_path / "off", data["retrieval_observer"], data["scorer"])
    on, on_llm, on_mcp = _pipeline(tmp_path / "on", data["retrieval_observer"], data["scorer"], data["observer"])
    baseline = off.process_post(post); result = on.process_post(post)
    assert _public(result) == _public(baseline) and off_llm.calls == on_llm.calls and off_mcp.calls == on_mcp.calls
    observation = result._candidate_calibration_shadow
    assert observation["status"] == "CALIBRATED_SHADOW_BOUND"
    assert observation["dataset_example_id"] == row["dataset_example_id"]
    assert type(observation["post_id"]) is int and type(observation["dataset_post_id"]) is str
    output = tmp_path / "saved"; output.mkdir()
    fields = _row_exporter(main_tree, output, data["scorer"], data["observer"])(result, 7, post.post_id)
    ref, saved_cal = fields["candidate_reranker_capture"], fields["candidate_calibration_shadow"]
    assert ref["status"] == "SAVED" and saved_cal["status"] == "CALIBRATED_SHADOW_BOUND"
    assert ref["observation_sha256"] == saved_cal["runtime_capture_sha256"]
    assert saved_cal["binding"] == ref["binding"] and saved_cal["binding"]["input_index"] == 7
    encoded = (output / ref["artifact"]["path"]).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == ref["artifact"]["sha256"]
    artifact = json.loads(encoded)
    assert artifact["observation"] == result._candidate_reranker_capture
    assert artifact["input_snapshot_sha256"] == INPUT_SHA
    baseline_row = {"post_id": post.post_id, "analysis_result": _public(baseline), "run_meta": {"stable": "same"}}
    with_fields = {**baseline_row, "run_meta": {"stable": "same", **fields}}
    assert _stable_result_payload(baseline_row) == _stable_result_payload(with_fields)


def test_new_unassigned_post_gets_capture_without_invented_probabilities(tmp_path, main_tree, frozen_bundle):
    data = frozen_bundle
    post = data["frozen_runtime_rows"][0]["post"].model_copy(deep=True); post.post_id = 29999
    pipe, _, _ = _pipeline(tmp_path / "new", data["retrieval_observer"], data["scorer"], data["observer"])
    result = pipe.process_post(post)
    output = tmp_path / "saved"; output.mkdir()
    fields = _row_exporter(main_tree, output, data["scorer"], data["observer"])(result, 8, post.post_id)
    assert fields["candidate_reranker_capture"]["status"] == "SAVED"
    receipt = fields["candidate_calibration_shadow"]
    assert receipt["status"] == "NOT_AVAILABLE" and receipt["reason_codes"] == ["FROZEN_ROW_NOT_ASSIGNED"]
    assert receipt["calibration_shadow"] is None and receipt["dataset_example_id"] is None


def test_main_capture_save_failure_cannot_leave_bound_calibration(tmp_path, main_tree, frozen_bundle):
    data = frozen_bundle; row = data["frozen_runtime_rows"][1]
    pipe, _, _ = _pipeline(tmp_path / "pipe", data["retrieval_observer"], data["scorer"], data["observer"])
    result = pipe.process_post(row["post"])
    output = tmp_path / "saved"; output.mkdir()
    exporter = _row_exporter(main_tree, output, data["scorer"], data["observer"])
    with patch.object(capture_storage, "export_candidate_capture_fields",
                      return_value={"candidate_reranker_capture": {"status": "NOT_AVAILABLE"}}):
        fields = exporter(result, 9, row["post"].post_id)
    assert fields["candidate_calibration_shadow"]["status"] == "NOT_AVAILABLE"
    assert fields["candidate_calibration_shadow"]["reason_codes"] == ["CAPTURE_STORAGE_NOT_BOUND"]
    assert fields["candidate_calibration_shadow"]["calibration_shadow"] is None


def test_source_only_early_route_removes_stale_observations_and_records_nonexecution(tmp_path, main_tree, frozen_bundle):
    stale_loop = next(n for n in ast.walk(main_tree) if isinstance(n, ast.For)
        and isinstance(n.target, ast.Name) and n.target.id == "stale_key"
        and any(isinstance(x, ast.Constant) and x.value == "candidate_reranker_capture" for x in ast.walk(n.iter)))
    run_meta = {"candidate_reranker_capture": {"status": "SAVED"},
                "candidate_calibration_shadow": {"status": "CALIBRATED_SHADOW_BOUND"}, "stable": "kept"}
    exec(compile(ast.Module(body=[stale_loop], type_ignores=[]), str(MAIN), "exec"), {"run_meta": run_meta})
    assert run_meta == {"stable": "kept"}
    fields = _row_exporter(main_tree, tmp_path, frozen_bundle["scorer"], frozen_bundle["observer"])(None, 10, 12006)
    assert fields["candidate_reranker_capture"]["status"] == "NOT_EXECUTED"
    assert fields["candidate_calibration_shadow"]["status"] == "NOT_EXECUTED"
    assert all(row["reason_codes"] == ["PIPELINE_NOT_EXECUTED"] for row in fields.values())
    assert not list(tmp_path.iterdir())
    with patch.object(capture_storage, "export_candidate_capture_fields", side_effect=AssertionError("OFF storage")):
        assert _row_exporter(main_tree, tmp_path, None, None)(None, 10, 12006) == {}


def test_paired_policy_rejects_calibration_observer_at_main_gate(main_tree):
    gate = next(n for n in ast.walk(main_tree) if isinstance(n, ast.If)
        and "_candidate_calibration" in {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)}
        and "_REQUESTED_PARALLEL_RAW" in {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)})
    namespace = {"_execution_settings": {"profile": "low-load-validation"}, "_REQUESTED_PARALLEL_RAW": 1,
        "_PARALLEL": 1, "_NO_DASHBOARD": False, "_CLI_ARGS": SimpleNamespace(reuse_shards_only=True),
        "_candidate_retrieval_observer": None, "_candidate_reranker": None, "_community_knowledge_snapshot": None,
        "_candidate_calibration": object(), "_candidate_semantics": None, "_candidate_inference": None,
        "_decision_call_measurement": {"slang_access_mode": "OFF"}}
    with pytest.raises(ValueError, match="연구 기능 OFF"):
        exec(compile(ast.Module(body=[gate], type_ignores=[]), str(MAIN), "exec"), namespace)
    namespace["_candidate_calibration"] = None
    exec(compile(ast.Module(body=[gate], type_ignores=[]), str(MAIN), "exec"), namespace)


def test_main_worker_policy_and_both_storage_branches_are_connected(main_tree):
    calls = [n for n in ast.walk(main_tree) if isinstance(n, ast.Call)]
    workers = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "AgenticPipeline"]
    assert any(any(k.arg == "candidate_calibration" and isinstance(k.value, ast.Name)
                   and k.value.id == "_candidate_calibration" for k in n.keywords) for n in workers)
    exports = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "_candidate_calibration_row_fields"]
    assert len(exports) == 2
    assert any(isinstance(n.args[0], ast.Constant) and n.args[0].value is None for n in exports)
    assert any(isinstance(n.args[0], ast.Name) and n.args[0].id == "result" for n in exports)
    policies = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "candidate_calibration_policy_fields"]
    assert len(policies) == 2  # 유효 실행 설정과 최종 manifest에 같은 producer 정책을 저장한다.


def test_execution_source_hashes_capture_and_calibration_runtime_dependencies():
    snapshot = source_snapshot(MAIN)
    paths = ("src/llm_batch/runtime/candidate_capture.py", "src/llm_batch/runtime/candidate_calibration.py",
        "src/llm_batch/grounding/candidate_reranker_capture.py", "src/llm_batch/grounding/candidate_reranker_calibration.py",
        "src/llm_batch/grounding/candidate_reranker_calibration_data.py", "src/llm_batch/grounding/candidate_reranker_event_bridge.py",
        "src/llm_batch/grounding/candidate_set_calibration_shadow.py", "src/llm_batch/grounding/reranker_training_split.py",
        "tools/run_candidate_reranker_training.py", "tools/run_candidate_reranker_calibration.py")
    for name in paths:
        assert snapshot["runtime_source_files"][name] == hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
