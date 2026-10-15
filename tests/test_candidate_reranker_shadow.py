"""Offline R4-B adapter contract tests. No trained scorer or semantic gold."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from llm_batch.grounding import candidate_reranker_shadow as reranker


def _write_manifest(tmp_path, scores=None, **changes):
    value = {"schema_version": reranker.MANIFEST_SCHEMA, "scorer_id": "synthetic-test-only",
        "backend": reranker.SYNTHETIC_BACKEND, "data_kind": "SYNTHETIC_FIXTURE",
        "feature_schema": reranker.FEATURE_SCHEMA,
        "scores": scores if scores is not None else [{"candidate_id": "corpus-b", "score": 2},
                                                    {"candidate_id": "corpus-a", "score": 2}]}
    value.update(changes)
    raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
    path = tmp_path / "synthetic-reranker.json"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def _scorer(tmp_path):
    path, digest = _write_manifest(tmp_path)
    return reranker.load_scorer(path, expected_sha256=digest)


def _learned_scorer(tmp_path):
    from llm_batch.grounding import candidate_reranker_learned as learned
    from test_candidate_reranker_learned import training_fixture
    manifest, sources, evidence, examples = training_fixture()
    trained = learned.train_model(manifest, source_payloads=sources, evidence_payloads=evidence,
                                  examples=examples, config={"epochs": 8})
    value = {"schema_version": reranker.LEARNED_MANIFEST_SCHEMA, "scorer_id": "trained-local-fixture",
             "backend": learned.BACKEND, "data_kind": "SYNTHETIC_FIXTURE",
             "feature_schema": learned.FEATURE_SCHEMA, "model": trained["model"]}
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    path = tmp_path / "learned-manifest.json"
    path.write_bytes(raw)
    scorer = reranker.load_scorer(path, expected_sha256=hashlib.sha256(raw).hexdigest())
    return scorer, path, value


def _nil_scorer(tmp_path):
    from llm_batch.grounding import candidate_reranker_nil_learned as learned
    from test_candidate_reranker_learned import training_fixture
    manifest, sources, evidence, examples = training_fixture(include_nil=True)
    trained = learned.train_model(manifest, source_payloads=sources, evidence_payloads=evidence,
                                  examples=examples)
    value = {"schema_version": reranker.NIL_MANIFEST_SCHEMA, "scorer_id": "nil-local-fixture",
             "backend": learned.BACKEND, "data_kind": "SYNTHETIC_FIXTURE",
             "feature_schema": learned.FEATURE_SCHEMA, "model": trained["model"]}
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    path = tmp_path / "nil-manifest.json"
    path.write_bytes(raw)
    scorer = reranker.load_scorer(path, expected_sha256=hashlib.sha256(raw).hexdigest())
    return scorer, path, value


def _semantic_scorer(tmp_path, *, head=False, with_alias=False):
    """실제 producer와 TRAIN optimizer를 통과한 새 모델. 고정 점수 대역이 아니다."""
    from test_candidate_reranker_semantic_training import semantic_training_fixture, _train, _artifact
    folder = tmp_path / "semantic-model"
    folder.mkdir(parents=True)
    bundle = semantic_training_fixture(folder / "training", with_alias=with_alias)
    model = _train(bundle, head=head)["model"]
    manifest = {"schema_version": reranker.NIL_MANIFEST_SCHEMA if head else reranker.LEARNED_MANIFEST_SCHEMA,
        "scorer_id": "semantic-consumption-local", "backend": model["backend"],
        "data_kind": model["data_kind"], "feature_schema": model["feature_schema"], "model": model}
    raw = json.dumps(manifest, ensure_ascii=False, allow_nan=False).encode("utf-8")
    path = folder / "model.json"
    path.write_bytes(raw)
    return reranker.load_scorer(path, expected_sha256=hashlib.sha256(raw).hexdigest()), bundle, _artifact(bundle)


@pytest.mark.parametrize("head", [False, True])
def test_semantic_model_adapter_requires_exact_replay_and_reports_actual_call(tmp_path, head):
    scorer, bundle, artifact = _semantic_scorer(tmp_path, head=head)
    view = artifact["enriched_view"]
    original = deepcopy(view)
    missing = scorer.score(view)
    assert missing["status"] == "INVALID_INPUT" and not missing["semantic_consumption"]["backend_invoked"]
    output = scorer.score(view, semantic_input=artifact, evidence_payloads=bundle[2])
    assert output["status"] == "SCORED_LEARNED", output
    consumed = output["semantic_consumption"]
    assert consumed["status"] == "SCORED" and consumed["input_validated"] and consumed["backend_invoked"] and consumed["score_produced"]
    assert consumed["semantic_input_sha256"] == output["semantic_input_sha256"] == artifact["input_sha256"]
    assert output["feature_schema"] == scorer.summary()["feature_schema"]
    assert output["candidate_observations"][0]["role_observations"] == view["candidates"][0]["role_observations"]
    assert output["nil_probability"] is output["selected_candidate_id"] is None
    assert output["public_apply"] is False and view == original
    if head:
        assert [r["label"] for r in output["event_logits"]] == [r["candidate_id"] for r in view["candidates"]] + ["__NIL__"]
    changed = deepcopy(artifact)
    changed["enriched_view"]["candidates"][0]["role_observations"][0]["role"] = "COMPARISON"
    changed["input_sha256"] = reranker.canonical_sha256({k:v for k,v in changed.items() if k != "input_sha256"})
    invalid = scorer.score(changed["enriched_view"], semantic_input=changed, evidence_payloads=bundle[2])
    assert invalid["status"] == "INVALID_INPUT" and not invalid["semantic_consumption"]["backend_invoked"]


def test_legacy_adapter_rejects_semantic_argument_without_changing_default_payload(tmp_path):
    scorer = _scorer(tmp_path)
    before = scorer.score(_view())
    rejected = scorer.score(_view(), semantic_input={})
    assert rejected["reason_codes"] == ["LEGACY_SEMANTIC_INPUT_FORBIDDEN"]
    assert "semantic_consumption" not in rejected
    after = scorer.score(_view())
    assert {k:v for k,v in before.items() if k != "latency_ms"} == {k:v for k,v in after.items() if k != "latency_ms"}


def test_nil_manifest_scores_frozen_events_without_probability_or_decision(tmp_path):
    from llm_batch.grounding import candidate_reranker_learned as base
    scorer, _, manifest = _nil_scorer(tmp_path)
    view = _view(); before = deepcopy(view)
    output = scorer.score(view)
    assert output["status"] == "SCORED_LEARNED" and output["backend"] == "NIL_AUGMENTED_LINEAR_V1"
    assert output["nil_head_available"] is True and output["data_kind"] == "SYNTHETIC_FIXTURE"
    assert output["training_status"] == "TRAINED_PAIRWISE_PLUS_NIL_HEAD"
    assert output["nil_probability"] is output["selected_candidate_id"] is None
    assert output["public_apply"] is output["publication_authority"] is False
    assert output["ranked_candidates"] == sorted(base.score_view(manifest["model"]["base_model"], view),
                                                 key=lambda row: (-row["score"], row["candidate_id"]))
    assert [row["label"] for row in output["event_logits"]] == [row["candidate_id"] for row in view["candidates"]] + ["__NIL__"]
    assert output["event_logits"][-1]["score"] == output["nil_score"]
    assert view == before
    assert "__NIL__" not in [row["candidate_id"] for row in output["ranked_candidates"]]


@pytest.mark.parametrize("fault", ["backend", "feature_schema", "data_kind", "model", "schema_list", "schema_dict"])
def test_nil_manifest_rejects_contract_or_model_changes(tmp_path, fault):
    _, path, value = _nil_scorer(tmp_path)
    if fault == "backend": value["backend"] = reranker.LEARNED_BACKEND
    if fault == "feature_schema": value["feature_schema"] = "unknown"
    if fault == "data_kind": value["data_kind"] = "SOURCE_BACKED"
    if fault == "model": value["model"]["model_sha256"] = "0" * 64
    if fault == "schema_list": value["schema_version"] = []
    if fault == "schema_dict": value["schema_version"] = {}
    raw = json.dumps(value, ensure_ascii=False).encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        reranker.load_scorer(path, expected_sha256=hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("state", ["TRUNCATED", "UNKNOWN", "EMPTY", "BYTE_LIMIT"])
def test_nil_unscored_states_do_not_invent_nil_scores(tmp_path, state):
    from unittest.mock import patch
    scorer, _, _ = _nil_scorer(tmp_path)
    view = _view()
    if state in {"TRUNCATED", "UNKNOWN"}: view["generation_status"] = state
    if state == "EMPTY": view["candidates"] = []
    if state == "BYTE_LIMIT":
        with patch.object(reranker, "MAX_RECEIPT_BYTES", 1200):
            output = scorer.score(view)
        assert output["status"] == "LIMIT_EXCEEDED"
    else:
        output = scorer.score(view)
        assert output["status"] != "SCORED_LEARNED"
    assert output["nil_score"] is None and output["event_logits"] == []
    assert output["nil_head_available"] is True


def test_learned_manifest_scores_unseen_ids_and_preserves_shadow_and_frozen_model(tmp_path):
    scorer, path, manifest = _learned_scorer(tmp_path)
    summary = scorer.summary()
    assert summary["status"] == "AVAILABLE_LEARNED" and summary["actual_model_available"] is True
    assert summary["data_kind"] == "SYNTHETIC_FIXTURE"
    assert summary["model_quality_status"] == "NOT_EVALUATED_BY_ADAPTER"
    assert summary["model_sha256"] == reranker.canonical_sha256(manifest["model"])
    assert summary["training_split_manifest_sha256"] == manifest["model"]["training_binding"]["split_manifest_sha256"]
    view = _view()
    before = deepcopy(view)
    path.write_text("changed after load", encoding="utf-8")
    manifest["model"].clear()
    result = scorer.score(view)
    assert result["status"] == "SCORED_LEARNED"
    assert result["training_status"] == "TRAINED_PAIRWISE_LINEAR"
    assert result["training_split_manifest_sha256"] == summary["training_split_manifest_sha256"]
    assert {r["candidate_id"] for r in result["ranked_candidates"]} == {"corpus-a", "corpus-b"}
    assert result["nil_probability"] is result["selected_candidate_id"] is None
    assert result["publication_authority"] is result["public_apply"] is result["central_db_write"] is False
    assert result["receipt_sha256"] == reranker.canonical_sha256({k:v for k,v in result.items()
        if k not in {"receipt_sha256", "latency_ms", "binding"}})
    assert view == before and scorer.summary() == summary


@pytest.mark.parametrize("fault", ["kind", "feature", "model", "extra"])
def test_learned_manifest_rejects_mismatched_kind_feature_weights_and_extra_fields(tmp_path, fault):
    _, path, value = _learned_scorer(tmp_path)
    if fault == "kind": value["data_kind"] = "SOURCE_BACKED"
    if fault == "feature": value["feature_schema"] = "unknown"
    if fault == "model": value["model"]["model_sha256"] = "0" * 64
    if fault == "extra": value["scores"] = []
    raw = json.dumps(value, ensure_ascii=False).encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        reranker.load_scorer(path, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_learned_backend_foreign_ids_fail_closed_and_truncated_view_never_scores(tmp_path, monkeypatch):
    from llm_batch.grounding import candidate_reranker_learned as learned
    scorer, _, _ = _learned_scorer(tmp_path)
    calls = []
    def bad(*args):
        calls.append(True)
        return [{"candidate_id": "foreign", "score": 3}, {"candidate_id": "corpus-a", "score": 2}]
    monkeypatch.setattr(learned, "score_view", bad)
    view = _view(); view["generation_status"] = "TRUNCATED"
    assert scorer.score(view)["status"] == "NOT_SCORED_GENERATION_TRUNCATED" and not calls
    view["generation_status"] = "COMPLETE"
    receipt = scorer.score(view)
    assert receipt["status"] == "ERROR" and receipt["reason_codes"] == ["BACKEND_ID_SET_MISMATCH"]
    assert not receipt["ranked_candidates"] and len(calls) == 1


def _source(post_id=7):
    return {"schema_version": reranker.SOURCE_SCHEMA, "post_id": post_id, "fragments": [
        {"raw_path": "/title", "kind": "TITLE", "text": "은빛 기록 비교"},
        {"raw_path": "/content_blocks/0/text", "kind": "BODY", "text": "과거 기록과 지금 기록"},
        {"raw_path": "/comments/0/content", "kind": "COMMENT", "text": "은빛 기록은 어때"}]}


def _role(role, path="/title", text="은빛", start=0):
    return {"role": role, "raw_path": path, "start": start, "end": start + len(text),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def _view(post_id=7):
    return {"schema_version": reranker.VIEW_SCHEMA, "stage": "PRE_SELECTION", "post_id": post_id,
        "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": "a" * 64,
        "source_view": _source(post_id), "candidate_set_fingerprint": None, "generation_status": "COMPLETE",
        "candidates": [{"candidate_id": candidate_id, "titles": ["합성 은빛 기록"], "urls": [],
            "aliases": [], "option_kind": "WORK_CANDIDATE", "event_eligible": True,
            "identity_conflict": False, "negative_evidence": [],
            "role_observations": [_role("PRIMARY"), _role("PREVIOUS", "/content_blocks/0/text", "과거")]
        } for candidate_id in ("corpus-b", "corpus-a")]}


def _assert_receipt(value):
    assert value["schema_version"] == reranker.RECEIPT_SCHEMA
    assert value["publication_authority"] is value["public_apply"] is value["central_db_write"] is False
    assert value["probability_status"] == "NOT_AVAILABLE_UNCALIBRATED"
    assert value["nil_probability"] is value["selected_candidate_id"] is None
    assert value["operational_effect"] == "NONE_SHADOW_ONLY"
    assert value["actual_model_available"] is False
    assert value["latency_ms"] >= 0
    assert value["receipt_digest_scope"] == reranker.DIGEST_SCOPE
    assert value["receipt_sha256"] == reranker.canonical_sha256({key: item for key, item in value.items()
        if key not in {"receipt_sha256", "latency_ms", "binding"}})
    assert len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= 49152


def test_frozen_synthetic_scores_ties_original_identity_and_role_observations(tmp_path):
    scorer = _scorer(tmp_path)
    source = _view()
    before = deepcopy(source)
    result = scorer.score(source)
    _assert_receipt(result)
    assert result["status"] == "SCORED_SYNTHETIC"
    assert result["training_status"] == "NOT_TRAINED_SYNTHETIC_FIXTURE"
    assert result["data_kind"] == "SYNTHETIC_FIXTURE"
    assert result["frozen_candidate_ids"] == ["corpus-b", "corpus-a"]
    assert result["ranked_candidates"] == [{"candidate_id": "corpus-a", "score": 2.0},
                                          {"candidate_id": "corpus-b", "score": 2.0}]
    assert result["candidate_observations"][0]["role_observations"] == before["candidates"][0]["role_observations"]
    assert result["candidate_option_bridge_status"] == "MISSING"
    assert result["candidate_set_fingerprint"] is None
    assert result["role_authority"] == "SOURCE_OBSERVATIONS_NOT_GOLD"
    assert result["input_sha256"] == reranker.canonical_sha256(before)
    assert result["query_sha256"] == reranker.canonical_sha256(before["source_view"])
    assert source == before
    result["candidate_observations"][0]["role_observations"].clear()
    assert source == before and scorer.score(source)["candidate_observations"][0]["role_observations"]
    assert "title" not in result["ranked_candidates"][0] and "url" not in result["ranked_candidates"][0]


def test_manifest_is_read_once_frozen_and_summary_is_independent(tmp_path):
    path, digest = _write_manifest(tmp_path)
    scorer = reranker.load_scorer(path, expected_sha256=digest)
    before = scorer.summary()
    path.write_text("invalid changed manifest", encoding="utf-8")
    modified = scorer.summary()
    modified["policy"]["max_candidates"] = 999
    assert scorer.summary() == before
    assert before["manifest_sha256"] == before["model_manifest_sha256"] == digest
    assert scorer.score(_view())["status"] == "SCORED_SYNTHETIC"
    with pytest.raises(FrozenInstanceError):
        scorer._scores = ()


@pytest.mark.parametrize("mutation,reason", [
    (lambda v: v.update(baseline_selected="corpus-a"), "FIELD_ALLOWLIST_INVALID"),
    (lambda v: v["candidates"][0].update(gold_label="WORK"), "FIELD_ALLOWLIST_INVALID"),
    (lambda v: v["source_view"].update(official_title="answer"), "FIELD_ALLOWLIST_INVALID"),
    (lambda v: v.update(stage="AFTER_SELECTION"), "VIEW_STAGE_OR_SCHEMA_INVALID"),
    (lambda v: v["candidates"][1].update(candidate_id="corpus-b"), "DUPLICATE_CANDIDATE_ID"),
    (lambda v: v["source_view"].update(post_id="7"), "SOURCE_BINDING_INVALID"),
    (lambda v: v.update(candidate_set_fingerprint="b" * 64), "UNDECLARED_CANDIDATE_OPTION_BRIDGE"),
    (lambda v: v["candidates"][0]["role_observations"][0].update(text_sha256="b" * 64), "ROLE_SPAN_SHA_MISMATCH"),
    (lambda v: v["candidates"][0]["role_observations"][0].update(role="GOLD_PRIMARY"), "ROLE_INVALID"),
    (lambda v: v["candidates"][0]["role_observations"][0].update(raw_path="/final/title"), "ROLE_SOURCE_MISSING"),
    (lambda v: v["candidates"][0]["role_observations"][0].update(start=True), "ROLE_SPAN_INVALID"),
])
def test_invalid_or_post_selection_features_are_rejected_before_backend(tmp_path, monkeypatch, mutation, reason):
    scorer = _scorer(tmp_path)
    calls = []
    monkeypatch.setattr(reranker, "_run_backend", lambda *args: calls.append(args))
    view = _view()
    mutation(view)
    before = deepcopy(view)
    result = scorer.score(view)
    _assert_receipt(result)
    assert result["status"] == "INVALID_INPUT" and result["reason_codes"] == [reason]
    assert calls == [] and view == before


@pytest.mark.parametrize("kind", ["candidates", "source_chars", "fragments", "roles", "input_bytes"])
def test_limits_refuse_whole_input_before_scoring_without_truncation(tmp_path, monkeypatch, kind):
    scorer = _scorer(tmp_path)
    calls = []
    monkeypatch.setattr(reranker, "_run_backend", lambda *args: calls.append(args))
    view = _view()
    if kind == "candidates":
        view["candidates"] = [dict(deepcopy(view["candidates"][0]), candidate_id=f"id-{i}") for i in range(21)]
    elif kind == "source_chars":
        view["source_view"]["fragments"][0]["text"] = "가" * 12001
    elif kind == "fragments":
        view["source_view"]["fragments"] = [{"raw_path": f"/comments/{i}", "kind": "COMMENT", "text": "x"} for i in range(129)]
    elif kind == "roles":
        view["candidates"][0]["role_observations"] = [_role("UNKNOWN") for _ in range(33)]
    else:
        view["candidates"] = [dict(deepcopy(view["candidates"][0]), candidate_id=f"id-{i}", titles=["가" * 1000] * 16) for i in range(4)]
    before = deepcopy(view)
    result = scorer.score(view)
    _assert_receipt(result)
    assert result["status"] == "LIMIT_EXCEEDED"
    assert result["ranked_candidates"] == [] and calls == [] and view == before


@pytest.mark.parametrize("kind", ["missing", "extra", "duplicate", "foreign", "nan", "inf", "bool", "metadata", "exception"])
def test_backend_output_must_preserve_exact_finite_candidate_id_set(tmp_path, monkeypatch, kind):
    scorer = _scorer(tmp_path)
    rows = [{"candidate_id": "corpus-a", "score": 2}, {"candidate_id": "corpus-b", "score": 1}]
    if kind == "missing":
        rows.pop()
    elif kind == "extra":
        rows.append({"candidate_id": "other", "score": 9})
    elif kind == "duplicate":
        rows[1]["candidate_id"] = "corpus-a"
    elif kind == "foreign":
        rows[1]["candidate_id"] = "other"
    elif kind in {"nan", "inf", "bool"}:
        rows[0]["score"] = {"nan": float("nan"), "inf": float("inf"), "bool": True}[kind]
    elif kind == "metadata":
        rows[0]["official_title"] = "forbidden"
    def backend(*_):
        if kind == "exception":
            raise RuntimeError("private backend error text must not enter receipt")
        return rows
    monkeypatch.setattr(reranker, "_run_backend", backend)
    result = scorer.score(_view())
    _assert_receipt(result)
    assert result["status"] == "ERROR" and result["ranked_candidates"] == []
    assert "private backend" not in json.dumps(result)


def test_backend_mutation_is_isolated_from_source_and_receipt(tmp_path, monkeypatch):
    scorer = _scorer(tmp_path)
    view = _view()
    before = deepcopy(view)
    def backend(_scores, candidates):
        candidates[0]["titles"].append("MUTATED")
        candidates[0]["role_observations"].clear()
        return [{"candidate_id": item["candidate_id"], "score": 0} for item in candidates]
    monkeypatch.setattr(reranker, "_run_backend", backend)
    result = scorer.score(view)
    assert view == before
    assert result["candidate_observations"][0]["role_observations"] == before["candidates"][0]["role_observations"]
    _assert_receipt(result)


@pytest.mark.parametrize("kind,status", [("unavailable", "UNAVAILABLE_MODEL"),
    ("empty", "EMPTY_CANDIDATE_SET"), ("source", "EMPTY_QUERY"),
    ("UNKNOWN", "NOT_SCORED_GENERATION_UNKNOWN"), ("TRUNCATED", "NOT_SCORED_GENERATION_TRUNCATED")])
def test_non_scored_terminal_states_are_honest(tmp_path, monkeypatch, kind, status):
    scorer = reranker.unavailable_scorer() if kind == "unavailable" else _scorer(tmp_path)
    calls = []
    monkeypatch.setattr(reranker, "_run_backend", lambda *args: calls.append(args))
    view = _view()
    if kind == "empty":
        view["candidates"] = []
    elif kind == "source":
        view["source_view"]["fragments"] = []
        for candidate in view["candidates"]:
            candidate["role_observations"] = []
    elif kind in {"UNKNOWN", "TRUNCATED"}:
        view["generation_status"] = kind
    result = scorer.score(view)
    _assert_receipt(result)
    assert result["status"] == status and not result["ranked_candidates"] and not calls


def test_missing_synthetic_score_is_not_default_zero_or_model_success(tmp_path):
    scorer = _scorer(tmp_path)
    view = _view()
    view["candidates"][0]["candidate_id"] = "unmapped"
    result = scorer.score(view)
    _assert_receipt(result)
    assert result["status"] == "ERROR" and result["reason_codes"] == ["SYNTHETIC_SCORE_MISSING"]


@pytest.mark.parametrize("changes,reason", [
    ({"backend": "import:some.package.load"}, "BACKEND_NOT_IMPLEMENTED"),
    ({"data_kind": "SOURCE_BACKED"}, "SYNTHETIC_BACKEND_REQUIRES_SYNTHETIC_DATA"),
    ({"weights_path": "model.pkl"}, "FIELD_ALLOWLIST_INVALID"),
    ({"scores": [{"candidate_id": "x", "score": True}]}, "SCORE_INVALID"),
    ({"scores": [{"candidate_id": "x", "score": float("nan")}]}, "SCORE_NONFINITE"),
    ({"scores": [{"candidate_id": "x", "score": 0}, {"candidate_id": "x", "score": 1}]}, "DUPLICATE_CANDIDATE_ID"),
])
def test_manifest_refuses_dynamic_or_untrained_claims_and_invalid_scores(tmp_path, changes, reason):
    path, digest = _write_manifest(tmp_path, **changes)
    with pytest.raises(reranker.CandidateRerankerShadowError) as error:
        reranker.load_scorer(path, expected_sha256=digest)
    assert error.value.code == reason


def test_loader_refuses_remote_hash_mismatch_and_duplicate_json(tmp_path):
    for path in ("https://invalid.test/model.json", r"\\invalid.test\model.json", "//invalid.test/model.json"):
        with pytest.raises(reranker.CandidateRerankerShadowError) as error:
            reranker.load_scorer(path, expected_sha256="a" * 64)
        assert error.value.code == "NONLOCAL_MANIFEST_PATH"
    path, digest = _write_manifest(tmp_path)
    with pytest.raises(reranker.CandidateRerankerShadowError, match="MANIFEST_SHA_MISMATCH"):
        reranker.load_scorer(path, expected_sha256="0" * 64)
    raw = b'{"schema_version":"x","schema_version":"x"}'
    path.write_bytes(raw)
    with pytest.raises(reranker.CandidateRerankerShadowError, match="DUPLICATE_JSON_KEY"):
        reranker.load_scorer(path, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_shared_frozen_scorer_concurrent_calls_preserve_each_source_and_digest(tmp_path):
    scorer = _scorer(tmp_path)
    views = [_view(i) for i in range(16)]
    before = deepcopy(views)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(scorer.score, views))
    assert views == before
    assert [result["post_id"] for result in results] == list(range(16))
    assert len({result["input_sha256"] for result in results}) == 16
    for value, view in zip(results, views):
        _assert_receipt(value)
        assert scorer.score(view)["receipt_sha256"] == value["receipt_sha256"]


def _actual_retrieval(tmp_path, top_k=20):
    from llm_batch.grounding.candidate_retrieval_shadow import candidate_content_sha256, load_corpus
    entries = []
    for suffix in ("b", "a"):
        title = "은빛 기록 " + suffix
        entries.append({"corpus_candidate_id": "corpus-" + suffix, "work_id": "work-" + suffix,
            "edition_id": "edition-" + suffix, "media_type": "WEB_NOVEL", "title": title,
            "aliases": [], "text": "은빛 기록", "content_sha256": candidate_content_sha256(title, [], "은빛 기록"),
            "sources": [{"source_ref": "fixture://" + suffix, "source_sha256": suffix * 64,
                "lineage_id": "synthetic-" + suffix, "observed_at": "2026-10-10T00:00:00Z",
                "rights": {"status": "SYNTHETIC_FIXTURE", "basis": "authored synthetic fixture"}}]})
    raw = json.dumps({"schema_version": "frozen_candidate_corpus_v1", "corpus_id": "synthetic-r4",
        "data_kind": "SYNTHETIC_FIXTURE", "entries": entries}, ensure_ascii=False).encode("utf-8")
    path = tmp_path / "synthetic-retrieval.json"
    path.write_bytes(raw)
    observer = load_corpus(path, expected_sha256=hashlib.sha256(raw).hexdigest(), top_k=top_k)
    return observer.observe(_source())


def test_actual_r2_to_frozen_view_to_synthetic_scorer_id_bridge_stays_missing(tmp_path):
    source = _source()
    retrieval = _actual_retrieval(tmp_path)
    before = deepcopy((source, retrieval))
    view = reranker.build_frozen_view(source, retrieval)
    result = _scorer(tmp_path).score(view)
    _assert_receipt(result)
    assert result["status"] == "SCORED_SYNTHETIC"
    assert view["generation_sha256"] == retrieval["observation_sha256"]
    assert view["generation_status"] == "COMPLETE"
    assert view["candidate_set_fingerprint"] is None
    assert view["candidate_namespace"] == "CORPUS_CANDIDATE"
    assert [candidate["candidate_id"] for candidate in view["candidates"]] == [row["corpus_candidate_id"] for row in retrieval["ranked_candidates"]]
    assert all(candidate["role_observations"] == [] for candidate in view["candidates"])
    assert (source, retrieval) == before
    view["source_view"]["fragments"][0]["text"] = "changed copy"
    assert (source, retrieval) == before


def test_r2_top_k_is_truncated_not_complete_or_nil(tmp_path):
    receipt = _actual_retrieval(tmp_path, top_k=1)
    view = reranker.build_frozen_view(_source(), receipt)
    assert view["generation_status"] == "TRUNCATED"
    result = _scorer(tmp_path).score(view)
    _assert_receipt(result)
    assert result["status"] == "NOT_SCORED_GENERATION_TRUNCATED"


@pytest.mark.parametrize("mutation,reason", [
    (lambda r: r.update(query_sha256="0" * 64), "RETRIEVAL_QUERY_SHA_MISMATCH"),
    (lambda r: r.update(post_id=999), "RETRIEVAL_RECEIPT_BINDING_INVALID"),
    (lambda r: r.update(public_apply=True), "RETRIEVAL_RECEIPT_BINDING_INVALID"),
    (lambda r: r["ranked_candidates"][0].update(title="tampered title"), "RETRIEVAL_RECEIPT_SHA_MISMATCH"),
    (lambda r: r.update(status="UNAVAILABLE_CORPUS"), "RETRIEVAL_UNAVAILABLE_CORPUS"),
])
def test_r2_bridge_rejects_cross_query_or_modified_upstream_receipt(tmp_path, mutation, reason):
    receipt = _actual_retrieval(tmp_path)
    mutation(receipt)
    with pytest.raises(reranker.CandidateRerankerShadowError) as error:
        reranker.build_frozen_view(_source(), receipt)
    assert error.value.code == reason


def test_exotic_inputs_fail_without_external_effect_or_leaking_exception_details(tmp_path):
    scorer = _scorer(tmp_path)
    circular = _view()
    circular["candidates"].append(circular)
    surrogate = _view()
    surrogate["source_view"]["fragments"][0]["text"] = "\ud800"
    for view in (None, object(), circular, surrogate):
        result = scorer.score(view)
        _assert_receipt(result)
        assert result["status"] in {"INVALID_INPUT", "LIMIT_EXCEEDED"}


@pytest.mark.parametrize("score", [0, -1])
def test_r2_positive_counts_cannot_bind_zero_or_negative_ranked_score(tmp_path, score):
    receipt = _actual_retrieval(tmp_path)
    receipt["ranked_candidates"][0]["score"] = score
    receipt["observation_sha256"] = reranker.canonical_sha256({key: value for key, value in receipt.items()
        if key not in {"observation_sha256", "latency_ms", "binding"}})
    before = deepcopy(receipt)
    with pytest.raises(reranker.CandidateRerankerShadowError) as error:
        reranker.build_frozen_view(_source(), receipt)
    assert error.value.code == "RETRIEVAL_POSITIVE_SCORE_REQUIRED" and receipt == before


@pytest.mark.parametrize("bad_status", [[], {}, None, 1, True])
def test_malformed_r2_status_uses_typed_error_contract(tmp_path, bad_status):
    receipt = _actual_retrieval(tmp_path)
    receipt["status"] = bad_status
    with pytest.raises(reranker.CandidateRerankerShadowError) as error:
        reranker.build_frozen_view(_source(), receipt)
    assert error.value.code == "RETRIEVAL_STATUS_INVALID"


@pytest.mark.parametrize("urls", [(), ("https://fixture.invalid/work/original",)])
def test_candidate_option_id_is_bound_by_existing_exact_identity_contract(tmp_path, urls):
    from llm_batch.grounding.candidate_set_shadow import CandidateOption, _candidate_id
    titles = ("합성 은빛 기록",)
    option = CandidateOption(candidate_id=_candidate_id(titles, urls), titles=titles, urls=urls)
    view = _view()
    view.update(candidate_namespace="CANDIDATE_OPTION", candidate_set_fingerprint="c" * 64)
    candidate = view["candidates"][0]
    candidate.update(candidate_id=option.candidate_id, titles=list(titles), urls=list(urls))
    view["candidates"] = [candidate]
    path, digest = _write_manifest(tmp_path, scores=[{"candidate_id": option.candidate_id, "score": 1}])
    scorer = reranker.load_scorer(path, expected_sha256=digest)
    good = scorer.score(view)
    _assert_receipt(good)
    assert good["status"] == "SCORED_SYNTHETIC" and good["candidate_option_bridge_status"] == "NOT_REQUIRED"
    if urls:
        candidate["urls"] = ["https://fixture.invalid/work/OTHER"]
    else:
        candidate["titles"] = ["완전히 다른 합성 작품"]
    before = deepcopy(view)
    bad = scorer.score(view)
    _assert_receipt(bad)
    assert bad["status"] == "INVALID_INPUT" and bad["reason_codes"] == ["CANDIDATE_OPTION_IDENTITY_INVALID"]
    assert view == before
