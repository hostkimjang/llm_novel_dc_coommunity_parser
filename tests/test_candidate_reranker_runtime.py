"""R4 실제 pipeline 연결·설정·저장·화면 API와 비간섭을 묶어 검증한다."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from llm_batch import agentic_pipeline as pipeline_module
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ExpertType
from llm_batch.grounding.candidate_reranker_shadow import load_scorer, unavailable_scorer
from llm_batch.runtime import candidate_reranker as runtime
from test_candidate_retrieval_pipeline import FakeLLM, FakeMCP, FakeExpert, _post, _public, no_external_or_extra_runtime
from test_candidate_retrieval_shadow import _entry, _corpus, _load

ROOT = Path(__file__).resolve().parents[1]


def setup_scorer(tmp_path):
    manifest = {"schema_version": "candidate_reranker_manifest_v1", "scorer_id": "r4-runtime-fixture",
                "backend": "SYNTHETIC_FIXED_SCORES_V1", "data_kind": "SYNTHETIC_FIXTURE",
                "feature_schema": "candidate_reranker_features_v1",
                "scores": [{"candidate_id": "alpha", "score": 0.2}, {"candidate_id": "beta", "score": 0.8}]}
    path = tmp_path / "model.json"
    raw = json.dumps(manifest, ensure_ascii=False).encode()
    path.write_bytes(raw)
    return load_scorer(path, expected_sha256=hashlib.sha256(raw).hexdigest()), path


def setup_retrieval(tmp_path, *, top_k=20):
    return _load(tmp_path, _corpus([
        _entry("alpha", title="오늘 저녁", aliases=[], text="국수 이야기"),
        _entry("beta", title="오늘 저녁 비교", aliases=[], text="따뜻한 음식"),
    ]), top_k=top_k)


def pipeline(tmp_path, observer, scorer=None):
    llm, mcp = FakeLLM(), FakeMCP()
    with patch.object(pipeline_module, "GatekeeperExpert", lambda client: FakeExpert(client, "gatekeeper")):
        pipe = AgenticPipeline(llm=llm, mcp=mcp, output_dir=tmp_path, parallel_count=1,
                              candidate_retrieval_shadow=observer, candidate_reranker_shadow=scorer)
    pipe.experts = {ExpertType.GATEKEEPER: FakeExpert(llm, "gatekeeper", pipe._search),
                    ExpertType.DISCOURSE: FakeExpert(llm, "discourse")}
    pipe.orchestrator.experts = pipe.experts
    pipe.orchestrator._try_fast_path = lambda *args, **kwargs: None
    return pipe, llm, mcp


def binding(post_id=901):
    return {"run_id": "r4-run", "input_index": 1, "post_id": post_id, "attempt_id": "attempt-r4", "publication_scope_id": "scope-r4"}


def observed(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    observer = setup_retrieval(tmp_path)
    post = _post()
    receipt = observer.observe(runtime._source_view(post))
    return scorer, observer, post, runtime.observe_candidate_reranker(scorer, post, receipt, observer)


def semantic_observed(tmp_path, *, head=True):
    from test_candidate_reranker_shadow import _semantic_scorer
    from test_candidate_semantics_alias_runtime import build_semantics_alias_runtime_fixture, _observe
    from llm_batch.domain.models import ContentBlock
    scorer, _, _ = _semantic_scorer(tmp_path / "model", head=head)
    context = tmp_path / "context"
    context.mkdir(parents=True)
    state = build_semantics_alias_runtime_fixture(context)
    state["post"] = state["post"].model_copy(deep=True, update={"content_blocks": [
        ContentBlock(type="text", text="나는 아생갤을 리뷰한다. 합성 별빛 도서관은 김하늘 작가의 전작이다. 합성후보")]})
    package = _observe(state)
    observed_value = runtime.observe_candidate_reranker_with_capture(scorer, state["post"],
        package["retrieval_receipt"], state["retrieval"], semantic_package=package, semantic_observer=state["observer"])
    assert observed_value["receipt"]["status"] == "SCORED_LEARNED", observed_value["receipt"]
    assert observed_value["capture"] is not None
    return scorer, state, package, observed_value


def test_semantic_runtime_consumes_verified_alias_and_roles_and_captures_same_call(tmp_path):
    scorer, state, package, value = semantic_observed(tmp_path)
    receipt, captured = value["receipt"], value["capture"]
    assert captured["schema_version"] == "candidate_reranker_capture_v2"
    assert captured["raw_receipt"] == receipt and captured["frozen_view"] == package["enriched_view"]
    assert captured["semantic_input"]["observation"] == package["observation"]
    assert sorted(captured["semantic_payloads_base64"]) == captured["semantic_input"]["alias_payload_sha256"]
    assert any("아생갤" in c["aliases"] for c in captured["frozen_view"]["candidates"])
    assert {r["role"] for c in captured["frozen_view"]["candidates"] for r in c["role_observations"]} >= {"PRIMARY", "PREVIOUS"}
    assert "preselection_role_producer" not in receipt
    result = SimpleNamespace(_candidate_reranker_shadow=receipt)
    saved = runtime.export_candidate_reranker_fields(result, scorer, binding=binding(state["post"].post_id))["candidate_reranker_shadow"]
    assert saved["receipt_sha256"] == receipt["receipt_sha256"] and saved["semantic_consumption"]["score_produced"]
    assert saved["nil_probability"] is saved["selected_candidate_id"] is None


@pytest.mark.parametrize("fault", ["missing", "other_source", "typed_id", "alias"])
def test_semantic_runtime_rejects_stale_package_before_backend(tmp_path, fault):
    scorer, state, package, _ = semantic_observed(tmp_path)
    source = state["post"].model_copy(deep=True)
    supplied = deepcopy(package)
    if fault == "missing": supplied = None
    elif fault == "other_source": source.title += " 바뀐 원문"
    elif fault == "typed_id": source.post_id = str(source.post_id)
    else:
        supplied["enriched_view"]["candidates"][0]["aliases"].append("위조별칭")
    retrieval = state["retrieval"].observe(runtime._source_view(source))
    with patch.object(type(scorer), "score", side_effect=AssertionError("invalid package reached model")) as called:
        result = runtime.observe_candidate_reranker_with_capture(scorer, source, retrieval, state["retrieval"],
            semantic_package=supplied, semantic_observer=state["observer"])
    assert called.call_count == 0 and result["capture"] is None
    assert result["receipt"]["semantic_consumption"]["backend_invoked"] is False
    assert result["receipt"]["ranked_candidates"] == []


def test_semantic_pipeline_cal_off_scores_once_before_experts_and_preserves_public(tmp_path):
    scorer, state, _, _ = semantic_observed(tmp_path)
    off, off_llm, off_mcp = pipeline(tmp_path / "off", state["retrieval"])
    on, on_llm, on_mcp = pipeline(tmp_path / "on", state["retrieval"], scorer)
    on._candidate_semantics = state["observer"]
    post = state["post"]
    baseline = off.process_post(post)
    real_score = type(scorer).score
    captured_inputs = []
    def score_once(self, view, **kwargs):
        assert not on_llm.calls and not on_mcp.calls
        captured_inputs.append(deepcopy(view))
        return real_score(self, view, **kwargs)
    with patch.object(type(scorer), "score", score_once):
        result = on.process_post(post)
    assert len(captured_inputs) == 1 and result._candidate_reranker_capture["frozen_view"] == captured_inputs[0]
    assert result._candidate_reranker_shadow["semantic_consumption"]["score_produced"]
    assert "_candidate_calibration_shadow" not in result.__dict__
    assert _public(result) == _public(baseline) and off_llm.calls == on_llm.calls and off_mcp.calls == on_mcp.calls


def test_cli_precedence_explicit_dependency_and_off_no_file_access():
    import expert_main
    args = expert_main._parse_args([])
    settings = runtime.resolve_candidate_reranker_settings(args, {})
    assert settings["mode"] == "OFF"
    with patch.object(Path, "open", side_effect=AssertionError("OFF read")):
        assert runtime.prepare_candidate_reranker(settings) is None
    assert runtime.export_candidate_reranker_fields(None, None, binding=binding()) == {}
    env = {"EXPERT_CANDIDATE_RERANKER": "SHADOW", "EXPERT_RERANKER_MANIFEST": "frozen.json",
           "EXPERT_RERANKER_MANIFEST_SHA256": "a" * 64}
    with pytest.raises(ValueError, match="candidate-retrieval"):
        runtime.resolve_candidate_reranker_settings(args, env)
    args = expert_main._parse_args(["--candidate-retrieval", "SHADOW"])
    assert runtime.resolve_candidate_reranker_settings(args, env)["sources"]["manifest_path"] == "ENVIRONMENT"
    args = expert_main._parse_args(["--candidate-reranker", "OFF", "--execution-profile", "low-load-validation"])
    assert runtime.resolve_candidate_reranker_settings(args, env)["mode"] == "OFF"


def test_explicit_bad_manifest_is_unavailable_without_fallback(tmp_path):
    import expert_main
    with pytest.raises(ValueError, match="SHA-256"):
        runtime.resolve_candidate_reranker_settings(expert_main._parse_args(["--candidate-reranker", "SHADOW", "--candidate-retrieval", "SHADOW"]), {})
    settings = {"mode": "SHADOW", "manifest_path": str(tmp_path / "missing.json"), "manifest_sha256": "a" * 64}
    value = runtime.prepare_candidate_reranker(settings)
    assert value.summary()["status"] == "UNAVAILABLE" and value.summary()["model_manifest_sha256"] == "a" * 64


def test_real_r2_freeze_scorer_process_export_and_public_noninterference(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    off, off_llm, off_mcp = pipeline(tmp_path / "off", retrieval)
    shadow, on_llm, on_mcp = pipeline(tmp_path / "shadow", retrieval, scorer)
    source = _post(); source.title = "오늘 저녁"; before = source.model_dump()
    baseline = off.process_post(source)
    called = []
    original_score = type(scorer).score
    def score_once(self, view):
        assert not on_llm.calls and not on_mcp.calls  # 실제 expert 시작 전에 freeze한다.
        called.append(deepcopy(view))
        return original_score(self, view)
    with patch.object(type(scorer), "score", score_once):
        result = shadow.process_post(source)
    receipt = result.__dict__["_candidate_reranker_shadow"]
    assert receipt["status"] == "SCORED_SYNTHETIC" and len(called) == 1
    observed_roles = [role for candidate in called[0]["candidates"] for role in candidate["role_observations"]]
    assert observed_roles and {role["role"] for role in observed_roles} == {"MENTIONED"}
    assert receipt["preselection_role_producer"]["status"] == "OBSERVED"
    assert [item["candidate_id"] for item in receipt["ranked_candidates"]] == ["beta", "alpha"]
    assert "REFERENCE_MUST_NOT_REACH_QUERY" not in json.dumps(called)
    assert "SEARCH_MUST_NOT_REACH_QUERY" not in json.dumps(called)
    assert _public(baseline) == _public(result)
    assert off_llm.calls == on_llm.calls and off_mcp.calls == on_mcp.calls
    assert source.model_dump() == before
    stored = runtime.export_candidate_reranker_fields(result, scorer, binding=binding())["candidate_reranker_shadow"]
    assert stored["receipt_sha256"] == receipt["receipt_sha256"]
    assert stored["binding"]["scope"] == "ATTEMPT_LOCAL_OBSERVATION"
    assert stored["candidate_option_bridge_status"] == "MISSING"
    assert stored["nil_probability"] is None and stored["actual_model_available"] is False
    stored["ranked_candidates"].clear()
    assert len(receipt["ranked_candidates"]) == 2 and "binding" not in receipt


def test_learned_backend_real_pipeline_export_and_public_noninterference(tmp_path):
    from test_candidate_reranker_shadow import _learned_scorer
    scorer, _, _ = _learned_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    off, off_llm, off_mcp = pipeline(tmp_path / "off", retrieval)
    shadow, on_llm, on_mcp = pipeline(tmp_path / "on", retrieval, scorer)
    baseline = off.process_post(_post())
    result = shadow.process_post(_post())
    receipt = result.__dict__["_candidate_reranker_shadow"]
    assert receipt["status"] == "SCORED_LEARNED" and receipt["actual_model_available"] is True
    assert receipt["data_kind"] == "SYNTHETIC_FIXTURE"
    assert {r["candidate_id"] for r in receipt["ranked_candidates"]} == {"alpha", "beta"}
    assert _public(result) == _public(baseline)
    assert off_llm.calls == on_llm.calls and off_mcp.calls == on_mcp.calls
    saved = runtime.export_candidate_reranker_fields(result, scorer, binding=binding())["candidate_reranker_shadow"]
    assert saved["status"] == "SCORED_LEARNED" and saved["model_sha256"] == scorer.summary()["model_sha256"]
    assert saved["receipt_sha256"] == receipt["receipt_sha256"] and saved["binding"] == {**binding(), "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    missing = runtime.export_candidate_reranker_fields(None, scorer, binding=binding())["candidate_reranker_shadow"]
    assert missing["status"] == "NOT_AVAILABLE" and missing["actual_model_available"] is True
    assert missing["ranked_candidates"] == [] and missing["reason_codes"] == ["PIPELINE_NOT_EXECUTED"]


def test_nil_backend_pipeline_producer_export_and_public_noninterference(tmp_path):
    from test_candidate_reranker_shadow import _nil_scorer
    scorer, _, _ = _nil_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    off, old_llm, old_mcp = pipeline(tmp_path / "off", retrieval)
    on, new_llm, new_mcp = pipeline(tmp_path / "on", retrieval, scorer)
    baseline, result = off.process_post(_post()), on.process_post(_post())
    receipt = result.__dict__["_candidate_reranker_shadow"]
    saved = runtime.export_candidate_reranker_fields(result, scorer, binding=binding())["candidate_reranker_shadow"]
    for value in (receipt, saved):
        assert value["status"] == "SCORED_LEARNED" and value["backend"] == "NIL_AUGMENTED_LINEAR_V1"
        assert value["preselection_role_producer"]["status"] == "OBSERVED"
        assert value["nil_head_available"] is True and type(value["nil_score"]) in (float, int)
        assert [item["label"] for item in value["event_logits"]] == value["frozen_candidate_ids"] + ["__NIL__"]
        assert value["nil_probability"] is value["selected_candidate_id"] is None
    assert _public(result) == _public(baseline)
    assert old_llm.calls == new_llm.calls and old_mcp.calls == new_mcp.calls
    missing = runtime.export_candidate_reranker_fields(None, scorer, binding=binding())["candidate_reranker_shadow"]
    assert missing["status"] == "NOT_AVAILABLE" and missing["nil_head_available"] is True
    assert missing["nil_score"] is None and missing["event_logits"] == []


@pytest.mark.parametrize("fault", ["nan", "boolean", "event_order", "event_score", "event_label", "probability", "head", "base_model"])
def test_nil_receipt_mutations_cannot_change_event_space_or_probability(tmp_path, fault):
    from test_candidate_reranker_shadow import _nil_scorer
    scorer, _, _ = _nil_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path); post = _post()
    receipt = runtime.observe_candidate_reranker(scorer, post, retrieval.observe(runtime._source_view(post)), retrieval)
    assert receipt["status"] == "SCORED_LEARNED"
    if fault == "nan": receipt["nil_score"] = float('nan')
    if fault == "boolean": receipt["nil_score"] = True
    if fault == "event_order": receipt["event_logits"].reverse()
    if fault == "event_score": receipt["event_logits"][0]["score"] += 1
    if fault == "event_label": receipt["event_logits"][0]["label"] = "foreign"
    if fault == "probability": receipt["nil_probability"] = 0.9
    if fault == "head": receipt["nil_head_available"] = False
    if fault == "base_model": receipt["candidate_ranker_model_sha256"] = "0" * 64
    if fault != "nan": runtime._seal(receipt)
    stored = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt), scorer,
        binding=binding())["candidate_reranker_shadow"]
    assert stored["status"] == "NOT_AVAILABLE" and stored["nil_score"] is None
    assert stored["event_logits"] == [] and stored["nil_probability"] is None


def test_explicit_view_export_rejects_reserved_nil_candidate_even_when_resealed(tmp_path):
    from test_candidate_reranker_shadow import _nil_scorer
    from llm_batch.grounding.candidate_reranker_shadow import build_frozen_view
    scorer, _, _ = _nil_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    source = runtime._source_view(_post())
    receipt = scorer.score(build_frozen_view(source, retrieval.observe(source)))
    original_id = receipt["frozen_candidate_ids"][0]
    receipt["frozen_candidate_ids"][0] = "__NIL__"
    for row in receipt["ranked_candidates"]:
        if row["candidate_id"] == original_id:
            row.update(candidate_id="__NIL__", score=receipt["nil_score"])
    receipt["ranked_candidates"].sort(key=lambda row: (-row["score"], row["candidate_id"]))
    receipt["candidate_observations"][0]["candidate_id"] = "__NIL__"
    receipt["event_logits"][0] = {"label": "__NIL__", "score": receipt["nil_score"]}
    runtime._seal(receipt)
    stored = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt), scorer,
        binding=binding())["candidate_reranker_shadow"]
    assert stored["status"] == "NOT_AVAILABLE"
    assert stored["ranked_candidates"] == stored["event_logits"] == [] and stored["nil_score"] is None


@pytest.mark.parametrize("fault", ["model", "kind", "availability", "backend", "training_split"])
def test_learned_receipt_mismatches_are_rejected_before_storage(tmp_path, fault):
    from test_candidate_reranker_shadow import _learned_scorer
    scorer, _, _ = _learned_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    post = _post()
    receipt = runtime.observe_candidate_reranker(scorer, post, retrieval.observe(runtime._source_view(post)), retrieval)
    if fault == "model": receipt["model_sha256"] = "0" * 64
    if fault == "kind": receipt["data_kind"] = "SOURCE_BACKED"
    if fault == "availability": receipt["actual_model_available"] = False
    if fault == "backend": receipt["backend"] = "SYNTHETIC_FIXED_SCORES_V1"
    if fault == "training_split": receipt["training_split_manifest_sha256"] = "0" * 64
    runtime._seal(receipt)
    result = SimpleNamespace(_candidate_reranker_shadow=receipt)
    stored = runtime.export_candidate_reranker_fields(result, scorer, binding=binding())["candidate_reranker_shadow"]
    assert stored["status"] == "NOT_AVAILABLE" and stored["reason_codes"] == ["INVALID_OR_OVERSIZED_RECEIPT"]
    assert not stored["ranked_candidates"]


@pytest.mark.parametrize("field", ["model_sha256", "model_kind", "model_quality_status", "training_split_manifest_sha256"])
def test_unscored_learned_receipt_cannot_rebind_model_metadata(tmp_path, field):
    from test_candidate_reranker_shadow import _learned_scorer
    scorer, _, _ = _learned_scorer(tmp_path)
    receipt = runtime.export_candidate_reranker_fields(None, scorer, binding=binding())["candidate_reranker_shadow"]
    receipt[field] = "0" * 64 if field.endswith("sha256") else "foreign"
    runtime._seal(receipt)
    stored = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt),
        scorer, binding=binding())["candidate_reranker_shadow"]
    assert stored["reason_codes"] == ["INVALID_OR_OVERSIZED_RECEIPT"]
    assert stored[field] == scorer.summary()[field] and not stored["ranked_candidates"]


@pytest.mark.parametrize("behavior", ["exception", "foreign_query", "foreign_model", "authority", "extra_id", "tamper_score", "summary_exception"])
def test_shadow_failures_preserve_actual_public_result(tmp_path, behavior):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    class Broken:
        def summary(self):
            if behavior == "summary_exception":
                raise RuntimeError("SECRET")
            return scorer.summary()
        def score(self, view):
            if behavior == "exception":
                raise RuntimeError("SECRET")
            output = scorer.score(view)
            if behavior == "foreign_query": output["query_sha256"] = "f" * 64
            if behavior == "foreign_model": output["scorer_sha256"] = "f" * 64
            if behavior == "authority": output["public_apply"] = True
            if behavior == "extra_id": output["ranked_candidates"].append({"candidate_id": "foreign", "score": 10})
            if behavior == "tamper_score": output["ranked_candidates"][0]["score"] = 50
            return output
    base, _, _ = pipeline(tmp_path / "base", retrieval)
    active, _, _ = pipeline(tmp_path / "active", retrieval, Broken())
    assert _public(base.process_post(_post())) == _public(result := active.process_post(_post()))
    receipt = result.__dict__["_candidate_reranker_shadow"]
    assert receipt["status"] == "ERROR" and not receipt["ranked_candidates"]
    assert "SECRET" not in json.dumps(receipt)


def test_empty_truncated_unavailable_and_retrieval_error_remain_distinct(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path, top_k=1)
    post = _post()
    upstream = retrieval.observe(runtime._source_view(post))
    assert runtime.observe_candidate_reranker(scorer, post, upstream, retrieval)["status"] == "NOT_SCORED_GENERATION_TRUNCATED"
    retrieval = setup_retrieval(tmp_path)
    upstream = retrieval.observe(runtime._source_view(post))
    assert runtime.observe_candidate_reranker(unavailable_scorer(), post, upstream, retrieval)["status"] == "UNAVAILABLE_MODEL"
    no_match = _post(); no_match.title = "없는표현"; no_match.content_blocks = []; no_match.comments = []
    upstream = retrieval.observe(runtime._source_view(no_match))
    assert runtime.observe_candidate_reranker(scorer, no_match, upstream, retrieval)["status"] == "EMPTY_CANDIDATE_SET"
    empty = _post(); empty.title = ""; empty.content_blocks = []; empty.comments = []
    upstream = retrieval.observe(runtime._source_view(empty))
    assert runtime.observe_candidate_reranker(scorer, empty, upstream, retrieval)["status"] == "EMPTY_QUERY"
    upstream = retrieval.observe(runtime._source_view(post)); upstream["status"] = "UNAVAILABLE_CORPUS"
    upstream["ranked_candidates"] = []
    upstream["observation_sha256"] = runtime._sha({k: v for k, v in upstream.items() if k not in {"latency_ms", "observation_sha256"}})
    value = runtime.observe_candidate_reranker(scorer, post, upstream, retrieval)
    assert value["status"] == "NOT_SCORED_GENERATION_UNKNOWN" and value["nil_probability"] is None


@pytest.mark.parametrize("mutation", ["query", "corpus", "count", "digest", "post", "score"])
def test_foreign_or_malformed_r2_observation_is_rejected(tmp_path, mutation):
    scorer, observer, post, _ = observed(tmp_path)
    receipt = observer.observe(runtime._source_view(post))
    if mutation == "query": receipt["query_sha256"] = "a" * 64
    if mutation == "corpus": receipt["corpus_sha256"] = "a" * 64
    if mutation == "count": receipt["counts"]["returned_candidates"] = False
    if mutation == "digest": receipt["observation_sha256"] = "a" * 64
    if mutation == "post": receipt["post_id"] = str(post.post_id)
    if mutation == "score": receipt["ranked_candidates"][0]["score"] = float("nan")
    assert runtime.observe_candidate_reranker(scorer, post, receipt, observer)["status"] == "ERROR"


@pytest.mark.parametrize("mutation", ["bool_score", "text_score", "order", "foreign_ids", "scope", "non_scored_rows"])
def test_rehashed_semantically_invalid_producer_receipts_are_rejected(tmp_path, mutation):
    scorer, observer, post, receipt = observed(tmp_path)
    def corrupt(value):
        value = deepcopy(value)
        if mutation == "bool_score": value["ranked_candidates"][0]["score"] = True
        if mutation == "text_score": value["ranked_candidates"][0]["score"] = "not-a-finite-number"
        if mutation == "order": value["ranked_candidates"].reverse()
        if mutation == "foreign_ids": value["frozen_candidate_ids"] = ["foreign-id"]
        if mutation == "scope": value["receipt_digest_scope"] = "UNRELATED_SCOPE"
        if mutation == "non_scored_rows": value["status"] = "UNAVAILABLE_MODEL"
        value["receipt_sha256"] = runtime._sha({k: v for k, v in value.items() if k not in {"latency_ms", "receipt_sha256", "binding"}})
        return value
    broken = SimpleNamespace(summary=scorer.summary, score=lambda view: corrupt(scorer.score(view)))
    upstream = observer.observe(runtime._source_view(post))
    assert runtime.observe_candidate_reranker(broken, post, upstream, observer)["status"] == "ERROR"
    saved = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=corrupt(receipt)), scorer, binding=binding())
    assert saved["candidate_reranker_shadow"]["status"] == "NOT_AVAILABLE"


def test_failed_retrieval_known_fingerprint_mismatch_is_not_honest_unavailability(tmp_path):
    scorer, observer, post, _ = observed(tmp_path)
    receipt = observer.observe(runtime._source_view(post))
    receipt.update(status="UNAVAILABLE_CORPUS", corpus_sha256="f" * 64, observation_sha256="f" * 64)
    assert runtime.observe_candidate_reranker(scorer, post, receipt, observer)["status"] == "ERROR"
    captured_failure = {"schema_version": "candidate_retrieval_shadow_v1", "mode": "SHADOW", "post_id": post.post_id,
                        "query_sha256": runtime._sha(runtime._source_view(post)), "status": "ERROR",
                        "publication_authority": False, "public_apply": False, "central_db_write": False}
    output = runtime.observe_candidate_reranker(scorer, post, captured_failure, observer)
    assert output["status"] == "NOT_SCORED_GENERATION_UNKNOWN"
    assert output["reason_codes"] == ["RETRIEVAL_ERROR"]


@pytest.mark.parametrize("mutation", ["post", "attempt", "model", "feature", "authority", "digest", "oversize", "trained"])
def test_storage_rejects_stale_foreign_or_changed_receipts(tmp_path, mutation):
    scorer, _, _, receipt = observed(tmp_path)
    assert receipt["status"] == "SCORED_SYNTHETIC"
    if mutation == "post": receipt["post_id"] = 902
    if mutation == "attempt": receipt["binding"] = {**binding(), "attempt_id": "old"}
    if mutation == "model": receipt["scorer_sha256"] = "a" * 64
    if mutation == "feature": receipt["feature_schema_sha256"] = "a" * 64
    if mutation == "authority": receipt["publication_authority"] = True
    if mutation == "digest": receipt["ranked_candidates"][0]["score"] = 999
    if mutation == "oversize": receipt["extra"] = "가" * 50000
    if mutation == "trained": receipt["actual_model_available"] = True
    saved = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt), scorer, binding=binding())["candidate_reranker_shadow"]
    assert saved["status"] == "NOT_AVAILABLE" and saved["scorer_sha256"] == scorer.summary()["scorer_sha256"]
    assert saved["receipt_sha256"] == runtime._seal(deepcopy(saved))["receipt_sha256"]


def test_early_route_missing_receipt_binding_limit_and_volatile_public_payload(tmp_path):
    from llm_batch.ledger.publication_commit import _stable_result_payload
    scorer, _, _, receipt = observed(tmp_path)
    early = runtime.export_candidate_reranker_fields(None, scorer, binding=binding())["candidate_reranker_shadow"]
    assert early["reason_codes"] == ["PIPELINE_NOT_EXECUTED"]
    huge = runtime.export_candidate_reranker_fields(None, scorer, binding={**binding(), "run_id": "한" * 65536})["candidate_reranker_shadow"]
    assert huge["reason_codes"] == ["BINDING_BYTE_LIMIT"] and "binding" not in huge
    assert len(runtime._bytes(huge)) < runtime.MAX_RECEIPT_BYTES
    base = {"post_id": 901, "analysis_result": {"identity": {}}, "run_meta": {}}
    rich = deepcopy(base); rich["run_meta"]["candidate_reranker_shadow"] = receipt
    assert _stable_result_payload(base) == _stable_result_payload(rich)
    assert runtime.candidate_reranker_policy_fields(scorer)["candidate_reranker_policy"]["model_input_may_change"] is False


def test_error_route_off_reuse_and_worker_isolation(tmp_path):
    scorer, _ = setup_scorer(tmp_path); observer = setup_retrieval(tmp_path)
    active, _, _ = pipeline(tmp_path / "active", observer, scorer)
    with patch.object(active.orchestrator, "process", side_effect=RuntimeError("expert failure")):
        output = active.process_post(_post())
    assert output.__dict__["_candidate_reranker_shadow"]["status"] == "SCORED_SYNTHETIC"
    active._candidate_reranker_shadow = None
    with patch.object(active, "_context_to_output", return_value=output):
        assert "_candidate_reranker_shadow" not in active.process_post(_post()).__dict__
    workers = [pipeline(tmp_path / f"worker-{i}", observer, scorer)[0] for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda item: item[1].process_post(_post(910 + item[0])), enumerate(workers)))
    receipts = [row.__dict__["_candidate_reranker_shadow"] for row in rows]
    assert [row["post_id"] for row in receipts] == [910, 911]
    assert all(row["status"] == "SCORED_SYNTHETIC" for row in receipts)
    assert receipts[0]["query_sha256"] != receipts[1]["query_sha256"]


def test_dashboard_details_retain_receipt_but_list_summaries_do_not(tmp_path):
    from llm_batch.monitor.server import _to_live_detail, _to_history_summary
    from llm_batch.monitor.run_index import row_meta, summary
    scorer, _, _, receipt = observed(tmp_path)
    fields = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt), scorer, binding=binding())
    row = {"post_id": 901, "analysis_result": {"identity": {}}, "run_meta": fields}
    assert _to_live_detail(row)["run_meta"]["candidate_reranker_shadow"] == fields["candidate_reranker_shadow"]
    assert row_meta(row)["candidate_reranker_shadow"]["binding"]["post_id"] == 901
    assert "candidate_reranker_shadow" not in json.dumps(_to_history_summary(row))
    assert summary(runtime.candidate_reranker_policy_fields(scorer))["candidate_reranker_policy"]["mode"] == "SHADOW"


@pytest.mark.parametrize("limited", [False, True])
def test_role_producer_failure_never_scores_or_changes_actual_pipeline(tmp_path, limited):
    scorer, _ = setup_scorer(tmp_path)
    observer = setup_retrieval(tmp_path)
    baseline, old_llm, old_mcp = pipeline(tmp_path / "off", observer)
    active, new_llm, new_mcp = pipeline(tmp_path / "on", observer, scorer)
    before = baseline.process_post(_post())
    error = RuntimeError("PRIVATE_PRODUCER_ERROR")
    if limited:
        error.code = "ROLE_OBSERVATION_LIMIT"
    with patch.object(runtime, "_observe_roles", side_effect=error) as producer, \
            patch.object(type(scorer), "score", side_effect=AssertionError("must not score")) as score:
        after = active.process_post(_post())
    receipt = after.__dict__["_candidate_reranker_shadow"]
    assert producer.call_count == 1 and score.call_count == 0
    assert receipt["status"] == ("LIMIT_EXCEEDED" if limited else "ERROR")
    assert not receipt["ranked_candidates"] and "PRIVATE_PRODUCER_ERROR" not in json.dumps(receipt)
    assert _public(before) == _public(after)
    assert old_llm.calls == new_llm.calls and old_mcp.calls == new_mcp.calls


def test_off_does_not_import_or_call_role_producer():
    import builtins
    real_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert "candidate_reranker_roles" not in name
        return real_import(name, *args, **kwargs)
    with patch.object(builtins, "__import__", guarded), \
            patch.object(runtime, "_observe_roles", side_effect=AssertionError("OFF producer")):
        assert runtime.observe_candidate_reranker(None, None, None, None) is None
        assert runtime.export_candidate_reranker_fields(None, None, binding=binding()) == {}
        assert runtime.candidate_reranker_policy_fields(None) == {}


def test_manual_frozen_view_receipt_is_validated_then_marked_not_produced(tmp_path):
    from llm_batch.grounding.candidate_reranker_shadow import build_frozen_view
    scorer, _ = setup_scorer(tmp_path)
    observer = setup_retrieval(tmp_path)
    source = runtime._source_view(_post())
    view = build_frozen_view(source, observer.observe(source))
    raw = scorer.score(view)
    before = deepcopy(raw)
    stored = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=raw),
        scorer, binding=binding())["candidate_reranker_shadow"]
    assert stored["status"] == "SCORED_SYNTHETIC"
    assert stored["ranked_candidates"] == raw["ranked_candidates"]
    metadata = stored["preselection_role_producer"]
    assert metadata["status"] == "NOT_EXECUTED"
    assert "EXPLICIT_FROZEN_VIEW_PROVIDED" in metadata["reason_codes"]
    assert metadata["frozen_view_sha256"] is None  # producer 미실행; 원래 input SHA는 receipt에 남는다.
    assert stored["input_sha256"] == raw["input_sha256"]
    assert raw == before
    raw["ranked_candidates"][0]["score"] = 99
    rejected = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=raw),
        scorer, binding=binding())["candidate_reranker_shadow"]
    assert rejected["status"] == "NOT_AVAILABLE" and not rejected["ranked_candidates"]


@pytest.mark.parametrize("mutation", ["source", "candidate", "semantic_role", "metadata_sha", "counts"])
def test_changed_producer_view_or_metadata_is_rejected_before_scoring(tmp_path, mutation):
    scorer, _ = setup_scorer(tmp_path)
    observer = setup_retrieval(tmp_path)
    post = _post(); post.title = "오늘 저녁"
    upstream = observer.observe(runtime._source_view(post))
    original = runtime._observe_roles
    def broken(view):
        enriched, metadata = original(view)
        if mutation == "source":
            enriched["source_view"]["fragments"][0]["text"] += " 위조"
        if mutation == "candidate":
            enriched["candidates"][0]["titles"] = ["다른 작품"]
        if mutation == "semantic_role":
            next(c for c in enriched["candidates"] if c["role_observations"])["role_observations"][0]["role"] = "PRIMARY"
        if mutation == "metadata_sha":
            metadata["frozen_view_sha256"] = "a" * 64
        if mutation == "counts":
            metadata["counts"]["candidates"] = True
        return enriched, metadata
    with patch.object(runtime, "_observe_roles", broken), \
            patch.object(type(scorer), "score", side_effect=AssertionError("invalid producer must not score")) as score:
        output = runtime.observe_candidate_reranker(scorer, post, upstream, observer)
    assert output["status"] == "ERROR" and score.call_count == 0 and not output["ranked_candidates"]
    assert output["preselection_role_producer"]["status"] == "ERROR"


@pytest.mark.parametrize("state", ["TRUNCATED", "UNKNOWN", "EMPTY_CANDIDATE_SET", "EMPTY_QUERY"])
def test_non_scoring_generation_skips_role_producer_and_preserves_terminal(tmp_path, state):
    scorer, _ = setup_scorer(tmp_path)
    observer = setup_retrieval(tmp_path, top_k=1 if state == "TRUNCATED" else 20)
    post = _post()
    if state == "EMPTY_CANDIDATE_SET":
        post.title, post.content_blocks, post.comments = "없는표현", [], []
    if state == "EMPTY_QUERY":
        post.title, post.content_blocks, post.comments = "", [], []
    upstream = observer.observe(runtime._source_view(post))
    if state == "UNKNOWN":
        upstream.update(status="UNAVAILABLE_CORPUS", ranked_candidates=[])
        upstream["observation_sha256"] = runtime._sha({k: v for k, v in upstream.items()
            if k not in {"latency_ms", "observation_sha256", "binding"}})
    with patch.object(runtime, "_observe_roles", side_effect=AssertionError("must skip")) as producer:
        output = runtime.observe_candidate_reranker(scorer, post, upstream, observer)
    expected = "NOT_SCORED_GENERATION_" + state if state in {"TRUNCATED", "UNKNOWN"} else state
    assert output["status"] == expected and producer.call_count == 0
    assert output["preselection_role_producer"]["status"] == "NOT_EXECUTED"
    assert not output["ranked_candidates"]
    stored = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=output),
        scorer, binding=binding())["candidate_reranker_shadow"]
    assert stored["status"] == expected


@pytest.mark.parametrize("unscored", [False, True])
@pytest.mark.parametrize("mutation", ["policy", "schema", "status", "sha", "counts", "reasons"])
def test_role_metadata_tampering_is_rejected_after_resealing_for_all_states(tmp_path, unscored, mutation):
    scorer, _, _, observed_receipt = observed(tmp_path)
    receipt = (runtime.export_candidate_reranker_fields(None, scorer, binding=binding())["candidate_reranker_shadow"]
               if unscored else observed_receipt)
    metadata = receipt["preselection_role_producer"]
    if mutation == "policy": metadata["policy_sha256"] = "f" * 64
    if mutation == "schema": metadata["schema_version"] = "foreign"
    if mutation == "status": metadata["status"] = "NOT_EXECUTED" if not unscored else "OBSERVED"
    if mutation == "sha": metadata["frozen_view_sha256"] = "f" * 64
    if mutation == "counts": metadata["counts"]["observations"] = True
    if mutation == "reasons": metadata["reason_codes"] = ["unbounded secret"]
    runtime._seal(receipt)
    output = runtime.export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt),
        scorer, binding=binding())["candidate_reranker_shadow"]
    assert output["status"] == "NOT_AVAILABLE" and output["reason_codes"] == ["INVALID_OR_OVERSIZED_RECEIPT"]
    assert output["preselection_role_producer"]["status"] == "NOT_EXECUTED"
    assert not output["ranked_candidates"]


def test_runtime_policy_and_receipt_share_producer_fingerprint(tmp_path):
    scorer, _, _, receipt = observed(tmp_path)
    policy = runtime.candidate_reranker_policy_fields(scorer)["candidate_reranker_policy"]["preselection_role_producer_policy"]
    assert policy["policy_sha256"] == runtime._sha(policy["policy"])
    assert receipt["preselection_role_producer"]["policy_sha256"] == policy["policy_sha256"]
    assert policy["policy"]["semantic_roles_supported"] == ["MENTIONED"]


def test_scorer_receipt_byte_limit_keeps_terminal_and_completed_role_metadata(tmp_path):
    from llm_batch.grounding import candidate_reranker_shadow as adapter
    scorer, _ = setup_scorer(tmp_path)
    observer = setup_retrieval(tmp_path)
    baseline, old_llm, old_mcp = pipeline(tmp_path / "off", observer)
    active, new_llm, new_mcp = pipeline(tmp_path / "on", observer, scorer)
    before = baseline.process_post(_post())
    original_score = type(scorer).score
    def limited_score(self, view):
        # 실제 adapter의 크기 제한 분기를 실행한다. R2 입력 검산 상한은 유지한다.
        with patch.object(adapter, "MAX_RECEIPT_BYTES", 1200):
            return original_score(self, view)
    with patch.object(type(scorer), "score", limited_score):
        after = active.process_post(_post())
    receipt = after.__dict__["_candidate_reranker_shadow"]
    saved = runtime.export_candidate_reranker_fields(after, scorer, binding=binding())["candidate_reranker_shadow"]
    for value in (receipt, saved):
        assert value["status"] == "LIMIT_EXCEEDED" and value["reason_codes"] == ["RECEIPT_BYTE_LIMIT"]
        assert value["details_available"] is False
        assert value["candidate_observations"] == value["ranked_candidates"] == []
        meta = value["preselection_role_producer"]
        assert meta["status"] == "OBSERVED" and meta["counts"]["observations"] > 0
        assert meta["frozen_view_sha256"] == value["input_sha256"]
        assert len(runtime._bytes(value)) < runtime.MAX_RECEIPT_BYTES
    assert _public(before) == _public(after)
    assert old_llm.calls == new_llm.calls and old_mcp.calls == new_mcp.calls
