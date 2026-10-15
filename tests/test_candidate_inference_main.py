"""일반 입력 inference의 실제 pipeline/main 저장·API 경계 회귀.

두 미배정 합성 입력에 실제 R2/의미 관측/NIL/CAL 소비기를 연결한다. 외부
전문가·검색만 대체하며 공개 결과, 호출, WAL과 과거 관측 배제 경계를 비교한다.
실제 자료의 품질을 증명하지 않는다. 실행은 root 통합 검증에서만 수행한다.
"""
import ast
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
from llm_batch.monitor import server
from llm_batch.monitor.run_index import RunIndex, bound_manifest, row_meta, summary
from llm_batch.runtime import candidate_inference as inference
from llm_batch.runtime.execution_config import source_snapshot
from test_candidate_retrieval_pipeline import (
    FakeLLM, FakeMCP, FakeExpert, _public, no_external_or_extra_runtime,
)

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "expert_main.py"
RUN_ID = "20261010_220000_123456"
SCOPE = "inference-main-scope"
INPUT_SHA = "a" * 64
FIELDS = {"candidate_reranker_inference", "candidate_inference_capture"}


@pytest.fixture(scope="module")
def main_tree():
    return ast.parse(MAIN.read_text(encoding="utf-8-sig"))


@pytest.fixture(scope="module")
def inference_bundle(tmp_path_factory):
    from tests.candidate_inference_fixtures import build_candidate_inference_fixture
    return build_candidate_inference_fixture(tmp_path_factory.mktemp("main-inference"))


def _pipeline(path, data, observer=None):
    llm, mcp = FakeLLM(), FakeMCP()
    with patch.object(pipeline_module, "GatekeeperExpert", lambda client: FakeExpert(client, "gatekeeper")):
        pipe = AgenticPipeline(llm=llm, mcp=mcp, output_dir=path, parallel_count=1,
            candidate_retrieval_shadow=data["retrieval_observer"], candidate_reranker_shadow=data["scorer"],
            candidate_semantics=data["semantic_observer"], candidate_inference=observer)
    pipe.experts = {ExpertType.GATEKEEPER: FakeExpert(llm, "gatekeeper", pipe._search),
                    ExpertType.DISCOURSE: FakeExpert(llm, "discourse")}
    pipe.orchestrator.experts = pipe.experts
    pipe.orchestrator._try_fast_path = lambda *args, **kwargs: None
    return pipe, llm, mcp


def _row_exporter(tree, path, data, observer):
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name == "_candidate_inference_row_fields")
    namespace = {"Any": Any, "Dict": Dict, "_candidate_inference": observer,
        "ts": RUN_ID, "publication_scope_id": SCOPE, "OUT_DIR": path,
        "_input_snapshot_sha256": INPUT_SHA,
        "_decision_call_row_attempt_id": lambda index, post_id: f"attempt-{index}-{post_id}",
        "_candidate_retrieval_observer": data["retrieval_observer"],
        "_candidate_semantics": data["semantic_observer"],
        "export_candidate_inference_fields": inference.export_candidate_inference_fields}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(MAIN), "exec"), namespace)
    return namespace[node.name]


def _startup(tree, args, environment, scorer=None):
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    body, collecting = [], False
    for node in main.body:
        assigned = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        if "_candidate_inference_settings" in assigned:
            collecting = True
        if collecting:
            body.append(node)
        if "_candidate_inference" in assigned:
            break
    assert len(body) >= 2
    namespace = {"_CLI_ARGS": args, "os": SimpleNamespace(environ=environment),
        "_candidate_reranker": scorer,
        "resolve_candidate_inference_settings": inference.resolve_candidate_inference_settings,
        "prepare_candidate_inference": inference.prepare_candidate_inference}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(MAIN), "exec"), namespace)
    return namespace["_candidate_inference_settings"], namespace["_candidate_inference"]


def test_main_default_off_and_cli_off_override_env_without_bundle_io(main_tree, monkeypatch):
    import expert_main
    monkeypatch.setattr(inference, "read_inference_bundle", lambda *a, **k: pytest.fail("OFF bundle IO"))
    settings, observer = _startup(main_tree, expert_main._parse_args([]), {})
    assert settings["mode"] == "OFF" and observer is None
    args = expert_main._parse_args(["--candidate-inference", "OFF"])
    settings, observer = _startup(main_tree, args, {"EXPERT_CANDIDATE_INFERENCE": "SHADOW",
        "EXPERT_INFERENCE_BUNDLE": "absent.json", "EXPERT_INFERENCE_BUNDLE_SHA256": "0" * 64})
    assert settings["sources"]["mode"] == "CLI" and settings["mode"] == "OFF" and observer is None


@pytest.mark.parametrize("use_env", [False, True])
def test_main_shadow_startup_loads_pinned_bundle_with_cli_precedence(main_tree, inference_bundle, use_env):
    import expert_main
    data = inference_bundle
    args = ["--candidate-retrieval", "SHADOW", "--candidate-reranker", "SHADOW"]
    values = {"EXPERT_CANDIDATE_INFERENCE": "SHADOW",
              "EXPERT_INFERENCE_BUNDLE": data["settings"]["bundle_path"],
              "EXPERT_INFERENCE_BUNDLE_SHA256": data["settings"]["bundle_sha256"]}
    if not use_env:
        args += ["--candidate-inference", "SHADOW", "--inference-bundle", data["settings"]["bundle_path"],
                 "--inference-bundle-sha256", data["settings"]["bundle_sha256"]]
        values = {"EXPERT_CANDIDATE_INFERENCE": "OFF", "EXPERT_INFERENCE_BUNDLE": "absent.json",
                  "EXPERT_INFERENCE_BUNDLE_SHA256": "0" * 64}
    settings, observer = _startup(main_tree, expert_main._parse_args(args), values, data["scorer"])
    assert observer.summary() == data["observer"].summary()
    assert set(settings["sources"].values()) == {"ENVIRONMENT" if use_env else "CLI"}


@pytest.mark.parametrize("retrieval,reranker", [("OFF", "OFF"), ("OFF", "SHADOW"), ("SHADOW", "OFF")])
def test_main_shadow_requires_explicit_dependencies(main_tree, retrieval, reranker):
    import expert_main
    args = expert_main._parse_args(["--candidate-retrieval", retrieval, "--candidate-reranker", reranker,
        "--candidate-inference", "SHADOW", "--inference-bundle", "missing.json",
        "--inference-bundle-sha256", "0" * 64])
    with pytest.raises(ValueError, match="RETRIEVAL_AND_RERANKER_SHADOW_REQUIRED"):
        _startup(main_tree, args, {})


def test_main_shadow_requires_pin_and_unavailable_scorer_stays_unavailable(main_tree):
    import expert_main
    argv = ["--candidate-retrieval", "SHADOW", "--candidate-reranker", "SHADOW", "--candidate-inference", "SHADOW"]
    with pytest.raises(ValueError, match="PINNED_BUNDLE_REQUIRED"):
        _startup(main_tree, expert_main._parse_args(argv), {})
    argv += ["--inference-bundle", "missing.json", "--inference-bundle-sha256", "0" * 64]
    _, observer = _startup(main_tree, expert_main._parse_args(argv), {}, None)
    assert observer.summary()["status"] == "UNAVAILABLE"
    assert observer.summary()["reason_codes"] == ["NIL_SCORER_REQUIRED"]


@pytest.mark.parametrize("row_index", [0, 1])
def test_two_unseen_posts_keep_public_experts_wal_and_save_actual_graph(tmp_path, main_tree, inference_bundle, row_index):
    data = inference_bundle
    post = data["rows"][row_index]["post"].model_copy(deep=True)
    before = post.model_dump(mode="json")
    inputs_before = {p: Path(p).read_bytes() for p in data["input_paths"]}
    off, off_llm, off_mcp = _pipeline(tmp_path / "off", data)
    on, on_llm, on_mcp = _pipeline(tmp_path / "on", data, data["observer"])
    baseline = off.process_post(post)
    observe = inference.observe_candidate_inference
    positions = []
    def before_experts(*args):
        assert not on_llm.calls and not on_mcp.calls
        positions.append(args[1].post_id)
        return observe(*args)
    with patch.object(inference, "observe_candidate_inference", before_experts):
        result = on.process_post(post)
    assert positions == [post.post_id]
    assert _public(result) == _public(baseline)
    assert off_llm.calls == on_llm.calls and len(on_llm.calls) == 2
    assert off_mcp.calls == on_mcp.calls and len(on_mcp.calls) == 1
    assert post.model_dump(mode="json") == before and "_candidate_inference" not in baseline.__dict__
    package = result._candidate_inference
    assert package["status"] == "TEMPERATURE_APPLIED_BOUND_INFERENCE", package
    assert package["capture_sha256"] == result._candidate_reranker_capture["capture_sha256"]
    assert package["graph"]["post_id"] == post.post_id
    assert str(post.post_id) not in {a.post_id for a in data["calibration_manifest"].assignments}
    assert package["inference"]["truth_status"] == "UNJUDGED_NOT_ASSIGNED"
    assert package["inference"]["evaluation_split"] is None and package["inference"]["actual_quality_evaluated"] is False
    assert sum(p["probability_mass"] for p in package["inference"]["event_probabilities"]) == 1000000
    output = tmp_path / "saved"
    fields = _row_exporter(main_tree, output, data, data["observer"])(result, row_index + 1, post)
    assert set(fields) == FIELDS
    saved, ref = fields["candidate_reranker_inference"], fields["candidate_inference_capture"]
    assert saved["status"] == "TEMPERATURE_APPLIED_BOUND_INFERENCE" and saved["score_replay_verified"] is True, saved
    assert ref["status"] == "SAVED" and saved["binding"] == ref["binding"]
    assert ref["binding"]["post_id"] == post.post_id and ref["binding"]["input_index"] == row_index + 1
    raw = (output / ref["artifact"]["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ref["artifact"]["sha256"] and len(raw) == ref["artifact"]["bytes"]
    artifact = json.loads(raw)
    assert artifact["capture"] == result._candidate_reranker_capture
    assert artifact["graph"] == package["graph"] and artifact["inference"] == package["inference"]
    assert artifact["input_snapshot_sha256"] == INPUT_SHA and artifact["score_replay_verified"] is True
    assert not list(output.rglob("*.pending"))
    baseline_row = {"post_id": post.post_id, "analysis_result": _public(baseline), "run_meta": {"stable": "same"}}
    with_fields = {**baseline_row, "run_meta": {"stable": "same", **fields}}
    assert _stable_result_payload(baseline_row) == _stable_result_payload(with_fields)
    assert all(saved[k] is False for k in ("publication_authority", "public_apply", "central_db_write", "action_applied"))
    assert inputs_before == {p: Path(p).read_bytes() for p in inputs_before}


def test_observer_exception_preserves_analysis_but_exports_missing_observation(tmp_path, main_tree, inference_bundle):
    data = inference_bundle; post = data["rows"][0]["post"]
    off, off_llm, off_mcp = _pipeline(tmp_path / "off", data)
    on, on_llm, on_mcp = _pipeline(tmp_path / "on", data, data["observer"])
    baseline = off.process_post(post)
    with patch.object(inference, "observe_candidate_inference", side_effect=RuntimeError("DO_NOT_EXPORT_SECRET")):
        result = on.process_post(post)
    assert _public(result) == _public(baseline) and off_llm.calls == on_llm.calls and off_mcp.calls == on_mcp.calls
    assert "_candidate_inference" not in result.__dict__ and result._candidate_reranker_capture is not None
    fields = _row_exporter(main_tree, tmp_path / "missing", data, data["observer"])(result, 1, post)
    saved = fields["candidate_reranker_inference"]
    assert saved["status"] == "NOT_AVAILABLE" and saved["reason_codes"] == ["INFERENCE_OBSERVATION_MISSING"]
    assert saved["inference"] is None and "DO_NOT_EXPORT_SECRET" not in json.dumps(fields)
    assert not (tmp_path / "missing").exists()


def test_expert_failure_retains_current_inference_and_reused_object_discards_it_when_off(tmp_path, inference_bundle):
    data = inference_bundle
    first, second = [r["post"] for r in data["rows"]]
    pipe, _, _ = _pipeline(tmp_path / "pipe", data, data["observer"])
    with patch.object(pipe.orchestrator, "process", side_effect=RuntimeError("synthetic expert failure")):
        result = pipe.process_post(first)
    assert "처리 오류:" in result.identity.reason
    assert result._candidate_inference["post_id"] == first.post_id
    assert result._candidate_reranker_capture["post_id"] == first.post_id
    pipe._candidate_inference = None
    with patch.object(pipe.orchestrator, "process", side_effect=RuntimeError("synthetic reuse")), \
         patch.object(pipe, "_error_output", return_value=result):
        reused = pipe.process_post(second)
    assert reused is result and "_candidate_inference" not in reused.__dict__
    assert reused._candidate_reranker_capture["post_id"] == second.post_id


def test_storage_failure_drops_probabilities_and_stale_package_cannot_bind(tmp_path, main_tree, inference_bundle):
    data = inference_bundle; post = data["rows"][1]["post"]
    pipe, _, _ = _pipeline(tmp_path / "pipe", data, data["observer"])
    result = pipe.process_post(post)
    exporter = _row_exporter(main_tree, tmp_path / "saved", data, data["observer"])
    with patch.object(inference, "_store_artifact", side_effect=OSError("PRIVATE_DISK_PATH")):
        fields = exporter(result, 2, post)
    assert fields["candidate_reranker_inference"]["status"] == "NOT_AVAILABLE"
    assert fields["candidate_reranker_inference"]["inference"] is None
    assert fields["candidate_inference_capture"]["artifact"] is None and "PRIVATE_DISK_PATH" not in json.dumps(fields)
    result.__dict__["_candidate_inference"] = deepcopy(data["rows"][0]["package"])
    fields = exporter(result, 2, post)
    assert fields["candidate_reranker_inference"]["reason_codes"] == ["INFERENCE_PACKAGE_REPLAY_MISMATCH"]
    assert fields["candidate_reranker_inference"]["inference"] is None
    assert not (tmp_path / "saved").exists()


def test_reuse_main_removes_stale_metadata_and_records_nonexecution(tmp_path, main_tree, inference_bundle):
    data = inference_bundle
    node = next(n for n in ast.walk(main_tree) if isinstance(n, ast.For)
        and isinstance(n.target, ast.Name) and n.target.id == "stale_key"
        and any(isinstance(x, ast.Constant) and x.value == "candidate_inference_capture" for x in ast.walk(n.iter)))
    meta = {"candidate_reranker_inference": {"status": "TEMPERATURE_APPLIED_BOUND_INFERENCE"},
            "candidate_inference_capture": {"status": "SAVED"}, "stable": "same"}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(MAIN), "exec"), {"run_meta": meta})
    assert meta == {"stable": "same"}
    fields = _row_exporter(main_tree, tmp_path / "on", data, data["observer"])(None, 1, data["rows"][0]["post"])
    assert set(fields) == FIELDS
    assert all(f["status"] == "NOT_EXECUTED" and f["reason_codes"] == ["PIPELINE_NOT_EXECUTED"] for f in fields.values())
    with patch.object(inference, "_store_artifact", side_effect=AssertionError("OFF storage")):
        assert _row_exporter(main_tree, tmp_path / "off", data, None)(None, 1, data["rows"][0]["post"]) == {}
    assert not list(tmp_path.iterdir())


def test_saved_runtime_metadata_reaches_live_history_index_and_manifest_without_source_edits(tmp_path, main_tree, inference_bundle, monkeypatch):
    data = inference_bundle; post = data["rows"][0]["post"]
    pipe, _, _ = _pipeline(tmp_path / "pipe", data, data["observer"])
    result = pipe.process_post(post)
    output = tmp_path / "out"
    fields = _row_exporter(main_tree, output, data, data["observer"])(result, 1, post)
    assert fields["candidate_inference_capture"]["status"] == "SAVED", fields
    policy = inference.candidate_inference_policy_fields(data["observer"], data["settings"])
    row = {"post_id": post.post_id, "title": post.title, "analysis_result": _public(result),
        "run_meta": {"run_id": RUN_ID, "publication_scope_id": SCOPE, **fields, "llm_endpoint": "PRIVATE_NOT_API"}}
    path = output / "result.json"
    manifest_path = output / "result_manifest.json"
    execution = {"schema_version": "expert_execution_config_v1", **policy}
    manifest = {"output_file": str(path), "run_id": RUN_ID, "publication_scope_id": SCOPE,
        "terminal_artifacts_finalized": True, "completed_count": 1, "input_post_count": 1,
        "execution_mode": "SYNTHETIC_FIXTURE", "execution_config": execution, **policy}
    path.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
    monkeypatch.setattr(server, "_OUT_DIR", output)
    index = RunIndex()
    records = index.records(output)
    assert len(records) == 1
    record = next(iter(records.values()))
    loaded = index.load_result(path, output)[0]
    live = server._to_live_detail(loaded, output_path=path)
    history = server._history_item(loaded, record)
    for detail in (live, history):
        assert detail["run_meta"] == row_meta(row)
        assert "llm_endpoint" not in detail["run_meta"]
        assert detail["run_manifest"]["binding_status"] == "BOUND"
        assert detail["run_manifest"]["summary"]["candidate_inference_policy"] == policy["candidate_inference_policy"]
        assert detail["run_manifest"]["summary"]["execution_config"] == execution
        for name in FIELDS:
            assert detail["run_meta"][name] == fields[name]
    assert record.public["manifest_summary"] == summary(manifest)
    assert before == {p: p.read_bytes() for p in before}
    for name in FIELDS:
        foreign = deepcopy(row)
        foreign["run_meta"][name]["binding"]["publication_scope_id"] = "foreign-scope"
        invalid = bound_manifest(path, output, item=foreign)
        assert invalid["binding_status"] == "MISMATCH" and invalid["summary"] == {}
        assert "PUBLICATION_SCOPE_ROW_CONFLICT" in invalid["reason_codes"]
    # root의 Node 검증이 같은 실제 exporter/API 자료를 소비한다. 별도 관측을 만들지 않는다.
    with (tmp_path / "general_inference_ui_readback.json").open("x", encoding="utf-8") as stream:
        json.dump({"live": live, "history": history}, stream, ensure_ascii=False, indent=2, allow_nan=False)


def test_main_policy_worker_exports_and_paired_off_gate_are_connected(main_tree):
    calls = [n for n in ast.walk(main_tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    workers = [n for n in calls if n.func.id == "AgenticPipeline"]
    assert any(any(k.arg == "candidate_inference" and isinstance(k.value, ast.Name)
        and k.value.id == "_candidate_inference" for k in n.keywords) for n in workers)
    exports = [n for n in calls if n.func.id == "_candidate_inference_row_fields"]
    assert len(exports) == 2
    assert any(isinstance(n.args[0], ast.Name) and n.args[0].id == "result" for n in exports)
    assert any(isinstance(n.args[0], ast.Constant) and n.args[0].value is None for n in exports)
    assert len([n for n in calls if n.func.id == "candidate_inference_policy_fields"]) == 2
    gate = next(n for n in ast.walk(main_tree) if isinstance(n, ast.If)
        and {"_candidate_inference", "_REQUESTED_PARALLEL_RAW"} <= {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)})
    namespace = {"_execution_settings": {"profile": "low-load-validation"}, "_REQUESTED_PARALLEL_RAW": 1,
        "_PARALLEL": 1, "_NO_DASHBOARD": False, "_CLI_ARGS": SimpleNamespace(reuse_shards_only=True),
        "_candidate_retrieval_observer": None, "_candidate_reranker": None, "_community_knowledge_snapshot": None,
        "_candidate_calibration": None, "_candidate_semantics": None, "_candidate_inference": object(),
        "_decision_call_measurement": {"slang_access_mode": "OFF"}}
    with pytest.raises(ValueError, match="연구 기능 OFF"):
        exec(compile(ast.Module(body=[gate], type_ignores=[]), str(MAIN), "exec"), namespace)
    namespace["_candidate_inference"] = None
    exec(compile(ast.Module(body=[gate], type_ignores=[]), str(MAIN), "exec"), namespace)


def test_execution_fingerprint_includes_inference_product_dependencies():
    snapshot = source_snapshot(MAIN)
    for relative in ("src/llm_batch/runtime/candidate_inference.py",
        "src/llm_batch/grounding/candidate_reranker_inference_graph.py",
        "src/llm_batch/grounding/candidate_reranker_calibration_inference.py",
        "tools/build_candidate_inference_bundle.py"):
        assert snapshot["runtime_source_files"][relative] == hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
