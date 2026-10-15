"""실제 선택 전 관측·main 저장·원문 재생과 기존 점수/공개 결과의 비간섭을 검증한다."""
import ast
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
from llm_batch.grounding import candidate_reranker_semantics as producer
from llm_batch.ledger.publication_commit import _stable_result_payload
from llm_batch.runtime import candidate_semantics as runtime
from llm_batch.runtime import candidate_reranker as reranker
from test_candidate_retrieval_pipeline import FakeLLM, FakeMCP, FakeExpert, _post, _public, no_external_or_extra_runtime
from test_candidate_reranker_runtime import setup_retrieval, setup_scorer, binding

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "expert_main.py"
INPUT_SHA = "a" * 64


@pytest.fixture(scope="module")
def main_tree():
    return ast.parse(MAIN.read_text(encoding="utf-8-sig"))


def pipeline(path, retrieval, scorer, observer):
    llm, mcp = FakeLLM(), FakeMCP()
    with patch.object(pipeline_module, "GatekeeperExpert", lambda client: FakeExpert(client, "gatekeeper")):
        pipe = AgenticPipeline(llm=llm, mcp=mcp, output_dir=path, parallel_count=1,
            candidate_retrieval_shadow=retrieval, candidate_reranker_shadow=scorer, candidate_semantics=observer)
    pipe.experts = {ExpertType.GATEKEEPER: FakeExpert(llm, "gatekeeper", pipe._search),
        ExpertType.DISCOURSE: FakeExpert(llm, "discourse")}
    pipe.orchestrator.experts = pipe.experts
    pipe.orchestrator._try_fast_path = lambda *a, **k: None
    return pipe, llm, mcp


def observed(tmp_path):
    retrieval, (scorer, _) = setup_retrieval(tmp_path), setup_scorer(tmp_path)
    observer = runtime.CandidateSemanticsObserver()
    post = _post()
    receipt = retrieval.observe(reranker._source_view(post))
    package = runtime.observe_candidate_semantics(observer, post, receipt, retrieval)
    assert package["status"] in runtime._EXECUTED, package
    return observer, package, retrieval, scorer, post


def export(tmp_path, observer, package, *, post=None, retrieval=None):
    if retrieval is None:
        folder = tmp_path / "export-context"
        folder.mkdir(exist_ok=True)
        retrieval = setup_retrieval(folder)
    return runtime.export_candidate_semantics_fields(SimpleNamespace(_candidate_reranker_semantics=package), observer,
        binding=binding(), output_dir=tmp_path / "output", input_snapshot_sha256=INPUT_SHA,
        current_post=post or _post(), retrieval_observer=retrieval)


def row_exporter(tree, path, observer, retrieval=None, scorer=None, calibration=None):
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_candidate_semantics_row_fields")
    namespace = {"Any": Any, "Dict": Dict, "_candidate_semantics": observer, "ts": "semantic-main",
        "publication_scope_id": "scope", "_decision_call_row_attempt_id": lambda i,p: f"attempt-{i}-{p}",
        "OUT_DIR": path, "_input_snapshot_sha256": INPUT_SHA, "_candidate_retrieval_observer": retrieval,
        "_candidate_reranker": scorer, "_candidate_calibration": calibration,
        "export_candidate_semantics_fields": runtime.export_candidate_semantics_fields}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(MAIN), "exec"), namespace)
    return namespace[node.name]


def test_semantic_consumption_envelope_binds_real_score_and_preserves_producer_claim(tmp_path, main_tree):
    from test_candidate_reranker_runtime import semantic_observed
    scorer, state, package, value = semantic_observed(tmp_path)
    result = SimpleNamespace(_candidate_reranker_semantics=package,
        _candidate_reranker_shadow=value["receipt"], _candidate_reranker_capture=value["capture"])
    fields = row_exporter(main_tree, tmp_path / "stored", state["observer"], state["retrieval"], scorer)(result, 1, state["post"])
    row = fields["candidate_reranker_semantics"]
    assert row["schema_version"] == "candidate_reranker_semantics_runtime_v2"
    assert row["consumption"]["status"] == "SCORED" and row["consumption"]["scorer_input_applied"] is True
    assert row["consumption"]["score_produced"] is True and row["consumption"]["calibration_input_applied"] is False
    assert row["consumption"]["score_receipt_sha256"] == value["receipt"]["receipt_sha256"]
    assert row["observation"]["score_consumption_status"] == "NOT_CONSUMED_MODEL_POLICY_UNBOUND"
    assert row["observation"] == package["observation"]
    assert fields["candidate_reranker_semantics_capture"]["status"] == "SAVED"
    value["receipt"]["receipt_sha256"] = "f" * 64
    invalid = row_exporter(main_tree, tmp_path / "invalid", state["observer"], state["retrieval"], scorer)(result, 1, state["post"])
    bad = invalid["candidate_reranker_semantics"]
    assert bad["observation"] == package["observation"] and bad["consumption"]["status"] == "NOT_AVAILABLE"
    assert bad["consumption"]["scorer_input_applied"] is None and bad["consumption"]["calibration_input_applied"] is None


def test_main_cli_default_off_precedence_and_explicit_retrieval_dependency():
    import expert_main
    args = expert_main._parse_args([])
    settings = runtime.resolve_candidate_semantics_settings(args, {})
    assert settings["mode"] == "OFF"
    with patch.object(Path, "open", side_effect=AssertionError("OFF 파일 읽기")):
        assert runtime.prepare_candidate_semantics(settings) is None
    env = {"EXPERT_CANDIDATE_SEMANTICS": "SHADOW", "EXPERT_SEMANTIC_ALIAS_BUNDLE": "unused.json",
        "EXPERT_SEMANTIC_ALIAS_BUNDLE_SHA256": "b" * 64}
    with pytest.raises(ValueError, match="RETRIEVAL_SHADOW_REQUIRED"):
        runtime.resolve_candidate_semantics_settings(args, env)
    args = expert_main._parse_args(["--candidate-semantics", "OFF"])
    assert runtime.resolve_candidate_semantics_settings(args, env)["mode"] == "OFF"
    args = expert_main._parse_args(["--candidate-semantics", "SHADOW", "--candidate-retrieval", "SHADOW"])
    settings = runtime.resolve_candidate_semantics_settings(args, {})
    assert runtime.prepare_candidate_semantics(settings).summary()["alias_bundle_sha256"] is None
    with pytest.raises(ValueError, match="PIN_REQUIRED"):
        runtime.resolve_candidate_semantics_settings(args, {"EXPERT_SEMANTIC_ALIAS_BUNDLE": "unpinned.json"})


def test_real_preselection_main_storage_preserves_public_and_legacy_score(tmp_path, main_tree):
    observer, _, retrieval, scorer, post = observed(tmp_path)
    baseline, off_llm, off_mcp = pipeline(tmp_path / "off", retrieval, scorer, None)
    enabled, on_llm, on_mcp = pipeline(tmp_path / "on", retrieval, scorer, observer)
    before = post.model_dump()
    legacy = baseline.process_post(post)
    with patch.object(producer, "observe_preselection_semantics", wraps=producer.observe_preselection_semantics) as called:
        result = enabled.process_post(post)
    assert called.call_count >= 1
    assert post.model_dump() == before and _public(result) == _public(legacy)
    assert off_llm.calls == on_llm.calls and off_mcp.calls == on_mcp.calls
    assert {k:v for k,v in result._candidate_reranker_shadow.items() if k != "latency_ms"} == {
        k:v for k,v in legacy._candidate_reranker_shadow.items() if k != "latency_ms"}
    fields = row_exporter(main_tree, tmp_path / "out", observer, retrieval)(result, 1, post)
    row, capture = fields["candidate_reranker_semantics"], fields["candidate_reranker_semantics_capture"]
    assert row["status"] in runtime._EXECUTED and row["consumption"]["status"] == "OBSERVED_NOT_CONSUMED"
    assert row["consumption"]["scorer_input_sha256"] == result._candidate_reranker_shadow["input_sha256"]
    assert not row["consumption"]["scorer_input_applied"] and not row["consumption"]["calibration_input_applied"]
    assert capture["status"] == "SAVED"
    ref = capture["artifact"]; raw = (tmp_path / "out" / ref["path"]).read_bytes()
    assert len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"]
    saved = json.loads(raw)
    assert saved["package"] == result._candidate_reranker_semantics
    assert saved["input_snapshot_sha256"] == INPUT_SHA and saved["binding"] == capture["binding"]
    runtime._validate_package(saved["package"], observer, post.post_id)
    assert runtime.read_candidate_semantics_capture(tmp_path / "out", ref) == saved
    public = _public(result)
    with_fields = {**public, "run_meta": fields}
    assert _stable_result_payload(with_fields) == _stable_result_payload({**public, "run_meta": {}})


def test_preselection_runs_before_expert_and_error_path_keeps_observation(tmp_path):
    observer, _, retrieval, scorer, post = observed(tmp_path)
    pipe, _, _ = pipeline(tmp_path / "on", retrieval, scorer, observer)
    seen = []
    original = producer.observe_preselection_semantics
    def observe(*a, **k):
        seen.append("semantics")
        return original(*a, **k)
    def fail(*a, **k):
        assert "semantics" in seen
        raise RuntimeError("injected expert failure")
    with patch.object(producer, "observe_preselection_semantics", side_effect=observe), patch.object(pipe.orchestrator, "process", side_effect=fail):
        result = pipe.process_post(post)
    assert result._candidate_reranker_semantics["status"] in runtime._EXECUTED
    assert "injected expert failure" in result.identity.reason


def test_producer_exception_is_visible_and_does_not_change_existing_analysis(tmp_path):
    observer, _, retrieval, scorer, post = observed(tmp_path)
    off, _, _ = pipeline(tmp_path / "off", retrieval, scorer, None)
    on, _, _ = pipeline(tmp_path / "on", retrieval, scorer, observer)
    baseline = off.process_post(post)
    with patch.object(producer, "observe_preselection_semantics", side_effect=ValueError("SEMANTICS_TEST_FAILURE")):
        result = on.process_post(post)
    assert _public(result) == _public(baseline)
    assert result._candidate_reranker_semantics["status"] == "ERROR"
    fields = export(tmp_path, observer, result._candidate_reranker_semantics)
    assert fields["candidate_reranker_semantics"]["reason_codes"] == ["SEMANTICS_TEST_FAILURE"]
    assert fields["candidate_reranker_semantics_capture"]["artifact"] is None


@pytest.mark.parametrize("field", ["post_id", "observer_sha256", "original_view", "enriched_view", "observation", "retrieval_receipt"])
def test_stale_or_resealed_private_package_is_not_exported(tmp_path, field):
    observer, package, *_ = observed(tmp_path)
    if field == "post_id": package[field] = str(package[field])
    elif field == "observer_sha256": package[field] = "f" * 64
    elif field == "original_view": package[field]["source_view"]["fragments"][0]["text"] += " changed"
    elif field == "enriched_view": package[field]["candidates"][0]["aliases"] = ["주입된 별칭"]
    elif field == "observation": package[field]["public_apply"] = True
    else: package[field]["scorer_sha256"] = "f" * 64
    fields = export(tmp_path, observer, package)
    assert fields["candidate_reranker_semantics"]["status"] == "NOT_AVAILABLE"
    assert fields["candidate_reranker_semantics"]["observation"] is None
    assert not (tmp_path / "output").exists()


def test_capture_write_failure_preserves_observation_but_never_reports_saved(tmp_path, monkeypatch):
    observer, package, *_ = observed(tmp_path)
    monkeypatch.setattr(runtime, "_publish", lambda *a, **k: (_ for _ in ()).throw(OSError("disk failure")))
    fields = export(tmp_path, observer, package)
    assert fields["candidate_reranker_semantics"]["status"] in runtime._EXECUTED
    assert fields["candidate_reranker_semantics_capture"]["status"] == "NOT_AVAILABLE"
    assert fields["candidate_reranker_semantics_capture"]["artifact"] is None


@pytest.mark.parametrize("changed", ["source", "corpus"])
def test_complete_valid_package_from_same_id_other_input_or_corpus_is_rejected(tmp_path, changed):
    observer, package, retrieval, _, post = observed(tmp_path)
    if changed == "source":
        post.title += " 다른 원문"
    else:
        from test_candidate_retrieval_shadow import _entry, _corpus, _load
        folder = tmp_path / "other-corpus"
        folder.mkdir()
        retrieval = _load(folder, _corpus([_entry("alpha", title="오늘 저녁", aliases=[], text="다른 판본")]))
    fields = export(tmp_path, observer, package, post=post, retrieval=retrieval)
    assert fields["candidate_reranker_semantics"]["reason_codes"] == ["SEMANTICS_CURRENT_CONTEXT_MISMATCH"]
    assert fields["candidate_reranker_semantics_capture"]["artifact"] is None
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("digest", [None, "a" * 64])
def test_optional_legacy_fingerprint_failure_does_not_discard_new_observation(tmp_path, digest):
    observer, package, retrieval, _, post = observed(tmp_path)
    result = SimpleNamespace(_candidate_reranker_semantics=package,
        _candidate_reranker_shadow={"post_id": post.post_id, "input_sha256": digest})
    from llm_batch.grounding import candidate_reranker_roles
    with patch.object(candidate_reranker_roles, "observe_preselection_roles", side_effect=ValueError("ROLE_OBSERVATION_LIMIT")):
        fields = runtime.export_candidate_semantics_fields(result, observer, binding=binding(),
            output_dir=tmp_path / "out", input_snapshot_sha256=INPUT_SHA, current_post=post, retrieval_observer=retrieval)
    assert fields["candidate_reranker_semantics"]["observation"] == package["observation"]
    assert fields["candidate_reranker_semantics"]["consumption"]["scorer_input_sha256"] is None
    assert fields["candidate_reranker_semantics_capture"]["status"] == "SAVED"


def test_not_executed_missing_and_off_are_distinct(tmp_path, main_tree):
    observer = runtime.CandidateSemanticsObserver()
    off = row_exporter(main_tree, tmp_path, None)(None, 1, _post())
    no_run = row_exporter(main_tree, tmp_path, observer)(None, 1, _post())
    missing = row_exporter(main_tree, tmp_path, observer)(SimpleNamespace(), 1, _post())
    assert off == {}
    assert no_run["candidate_reranker_semantics"]["status"] == "NOT_EXECUTED"
    assert no_run["candidate_reranker_semantics"]["consumption"]["status"] == "NOT_EXECUTED"
    assert missing["candidate_reranker_semantics"]["status"] == "NOT_AVAILABLE"
    assert not (tmp_path / "candidate_semantics_captures").exists()


def test_concurrent_calls_do_not_share_observation_and_off_clears_reused_result(tmp_path):
    observer, _, retrieval, scorer, _ = observed(tmp_path)
    pipe, _, _ = pipeline(tmp_path / "on", retrieval, scorer, observer)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(pipe.process_post, [_post(902), _post(903)]))
    assert [r._candidate_reranker_semantics["post_id"] for r in results] == [902, 903]
    assert results[0]._candidate_reranker_semantics is not results[1]._candidate_reranker_semantics
    old = results[0]
    pipe._candidate_semantics = None
    with patch.object(pipe.orchestrator, "process", side_effect=RuntimeError("synthetic reuse")), \
         patch.object(pipe, "_error_output", return_value=old):
        reused = pipe.process_post(_post(904))
    assert reused is old and "_candidate_reranker_semantics" not in old.__dict__


def test_main_paired_gate_worker_startup_storage_and_source_manifest(main_tree):
    calls = [n for n in ast.walk(main_tree) if isinstance(n, ast.Call)]
    workers = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "AgenticPipeline"]
    assert any(any(k.arg == "candidate_semantics" and isinstance(k.value, ast.Name)
        and k.value.id == "_candidate_semantics" for k in n.keywords) for n in workers)
    assert len([n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "_candidate_semantics_row_fields"]) == 2
    assert len([n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "candidate_semantics_policy_fields"]) == 2
    gate = next(n for n in ast.walk(main_tree) if isinstance(n, ast.If)
        and "_candidate_semantics" in {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)}
        and "_REQUESTED_PARALLEL_RAW" in {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)})
    namespace = {"_execution_settings": {"profile": "low-load-validation"}, "_REQUESTED_PARALLEL_RAW": 1,
        "_PARALLEL": 1, "_NO_DASHBOARD": False, "_CLI_ARGS": SimpleNamespace(reuse_shards_only=True),
        "_candidate_retrieval_observer": None, "_candidate_reranker": None, "_community_knowledge_snapshot": None,
        "_candidate_calibration": None, "_candidate_semantics": object(), "_candidate_inference": None,
        "_decision_call_measurement": {"slang_access_mode": "OFF"}}
    with pytest.raises(ValueError, match="연구 기능 OFF"):
        exec(compile(ast.Module(body=[gate], type_ignores=[]), str(MAIN), "exec"), namespace)
    namespace["_candidate_semantics"] = None
    exec(compile(ast.Module(body=[gate], type_ignores=[]), str(MAIN), "exec"), namespace)
    from llm_batch.runtime.execution_config import source_snapshot
    current = source_snapshot(MAIN)["runtime_source_files"]
    for name in ("src/llm_batch/runtime/candidate_semantics.py", "src/llm_batch/grounding/candidate_reranker_semantics.py",
        "src/llm_batch/grounding/candidate_reranker_alias_evidence.py"):
        assert current[name] == hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
