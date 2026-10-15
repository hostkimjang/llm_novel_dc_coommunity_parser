"""전체 FROZEN 분모·고정 NIL/CAL graph 평가의 합성 회귀. 실행은 통합 runner 전용."""
from copy import deepcopy
from types import SimpleNamespace
import hashlib
import json

import pytest

from src.llm_batch.measurement import candidate_reranker_nil_evaluation as evaluation
from src.llm_batch.grounding import candidate_reranker_calibration as temperature
from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.grounding import candidate_set_calibration_shadow as legacy
from src.llm_batch.grounding import reranker_training_split as split
from src.llm_batch.runtime.candidate_reranker import export_candidate_reranker_fields
from candidate_reranker_calibration_fixtures import build_calibration_fixture, bind_graph


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def reseal(receipt):
    receipt["receipt_sha256"] = evaluation.canonical_sha256({k: v for k, v in receipt.items()
        if k not in {"receipt_sha256", "latency_ms", "binding"}})
    return receipt


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    return build_calibration_fixture(tmp_path_factory.mktemp("nil-frozen-evaluation"))


@pytest.fixture(scope="module")
def artifact(bundle):
    return temperature.fit_temperature(bundle["calibration_events"],
        split_manifest=bundle["calibration_manifest"], policy=bundle["policy"])["artifact"]


def inputs(bundle, artifact):
    expected, observations, graphs = [], [], []
    by_id = {r["assignment"]["example_id"]: r for r in bundle["training_manifest"]["rows"]}
    for args in bundle["frozen_args"]:
        example = deepcopy(args["example"])
        eid = example["example_id"]
        scope = args["publication_scope_id"]
        receipt = deepcopy(args["raw_receipt"])
        receipt["binding"] = {**by_id[eid]["binding"], "post_id": by_id[eid]["assignment"]["post_id"],
            "publication_scope_id": scope, "scope": "ATTEMPT_LOCAL_OBSERVATION"}
        expected.append({**example, "publication_scope_id": scope})
        observations.append({"example_id": eid, "receipt": receipt})
        graph = {k: args[k] for k in evaluation.GRAPH_KEYS}
        graph["example"], graph["raw_receipt"] = deepcopy(example), deepcopy(args["raw_receipt"])
        graphs.append(graph)
    return {**bundle["common_kwargs"], "training_manifest": deepcopy(bundle["training_manifest"]),
        "scorer_summary": deepcopy(bundle["scorer_summary"]), "source_payloads": dict(bundle["source_payloads"]),
        "evidence_payloads": dict(bundle["evidence_payloads"]), "expected_rows": expected,
        "observations": observations, "frozen_rows": graphs, "policy": bundle["policy"],
        "calibration_artifact": artifact}


def snapshot(args):
    return encoded({**{k: v for k, v in args.items() if k not in
        {"source_payloads", "evidence_payloads", "frozen_rows", "policy", "calibration_manifest", "calibration_artifact"}},
        "source": {k: hashlib.sha256(v).hexdigest() for k, v in args["source_payloads"].items()},
        "evidence": {k: hashlib.sha256(v).hexdigest() for k, v in args["evidence_payloads"].items()},
        "graphs": [evaluation._graph_payload(g) for g in args["frozen_rows"]],
        "policy": args["policy"].to_dict(), "calibration": args["calibration_manifest"].to_dict(),
        "artifact": args["calibration_artifact"].to_dict() if args["calibration_artifact"] else None})


def recap(args, index):
    exp = args["expected_rows"][index]
    prior = json.loads(args["evidence_payloads"][exp["capture_sha256"]])
    prior["frozen_view_sha256"] = evaluation.canonical_sha256(exp["frozen_view"])
    prior["candidate_text_bindings_sha256"] = evaluation.canonical_sha256(exp["candidate_text_bindings"])
    raw = encoded(prior)
    exp["capture_sha256"] = hashlib.sha256(raw).hexdigest()
    args["evidence_payloads"][exp["capture_sha256"]] = raw


def rescore(args, bundle, index):
    binding = args["observations"][index]["receipt"]["binding"]
    receipt = bundle["scorer"].score(args["expected_rows"][index]["frozen_view"])
    args["observations"][index]["receipt"] = {**receipt, "binding": binding}
    recap(args, index)


def rebind_graph(args, index):
    graph = args["frozen_rows"][index]
    graph["example"] = {k: deepcopy(v) for k, v in args["expected_rows"][index].items() if k != "publication_scope_id"}
    graph["raw_receipt"] = deepcopy(args["observations"][index]["receipt"])
    context = {**args, **graph}
    bind_graph(context)
    graph["source_binding_sha256"] = context["source_binding_sha256"]


def test_full_actual_synthetic_model_and_cal_fixture_equals_existing_holdout(bundle, artifact, monkeypatch):
    args = inputs(bundle, artifact)
    before = snapshot(args)
    monkeypatch.setattr(temperature, "fit_temperature", lambda *a, **k: pytest.fail("new CAL fit forbidden"))
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert before == snapshot(args)
    assert report == evaluation.evaluate_frozen_nil_scores(**args)
    assert report["schema_version"] == evaluation.SCHEMA
    assert report["report_sha256"] == evaluation.canonical_sha256({k: v for k, v in report.items() if k != "report_sha256"})
    assert report["counts"]["expected_rows"] == report["counts"]["observed_rows"] == 2
    assert report["counts"]["calibration_bound_rows"] == 2
    assert report["counts"]["truth_kinds"] == {"CANDIDATE": 1, "NIL": 1}
    shadows = {eid: legacy.build_calibration_shadow(base, bundle["frozen_vectors"][eid], artifact,
        bundle["policy"], split_manifest=bundle["calibration_manifest"], assignment=bundle["frozen_assignments"][eid])
        for eid, base in bundle["frozen_base_shadows"].items()}
    expected = legacy.evaluate_frozen_holdout(split_manifest=bundle["calibration_manifest"], shadows=shadows,
        policy=bundle["policy"], evidence_mode="SYNTHETIC_CONTRACT_ONLY",
        base_shadows=bundle["frozen_base_shadows"], score_vectors=bundle["frozen_vectors"], calibration_artifact=artifact)
    assert report["calibration_evaluation"] == expected
    assert report["rank_metrics"]["mrr_scored_work"]["denominator"] == 1
    assert report["rank_metrics"]["score_coverage"]["denominator"] == 2
    assert all("__NIL__" not in row["ranked_candidate_ids"] for row in report["rows"])
    assert report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert all(report[key] is False for key in ("quality_acceptance_claimed", "publication_authority",
        "public_apply", "central_db_write", "actual_quality_evaluated", "new_calibration_fit_executed"))


@pytest.mark.parametrize("keep", [0, 1])
def test_partial_graph_keeps_full_denominator_and_never_partial_calibration_metrics(bundle, artifact, keep):
    args = inputs(bundle, artifact)
    args["frozen_rows"] = args["frozen_rows"][:keep]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["counts"]["expected_rows"] == 2 and len(report["rows"]) == 2
    assert report["counts"]["calibration_bound_rows"] == keep
    assert report["status"] == report["calibration_evaluation"]["status"] == "NOT_EVALUABLE"
    assert all(v is None for v in report["calibration_evaluation"]["metrics"].values())
    assert report["rank_metrics"]["score_coverage"]["value"] == 1


def test_missing_artifact_preserves_valid_graph_and_raw_accounting(bundle):
    report = evaluation.evaluate_frozen_nil_scores(**inputs(bundle, None))
    assert report["counts"]["graph_rows"] == 2 and report["counts"]["calibration_bound_rows"] == 0
    assert all("CALIBRATION_ARTIFACT_MISSING" in r["calibration_reason_codes"] for r in report["rows"])


@pytest.mark.parametrize("status", ["ERROR", "LIMIT_EXCEEDED", "UNAVAILABLE_MODEL", "INVALID_INPUT", "NOT_AVAILABLE"])
def test_failure_terminals_are_not_nil_or_removed(bundle, artifact, status):
    args = inputs(bundle, artifact)
    receipt = args["observations"][0]["receipt"]
    receipt.update(status=status, ranked_candidates=[], nil_score=None, event_logits=[])
    reseal(receipt)
    args["frozen_rows"] = args["frozen_rows"][1:]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["counts"]["source_terminals"][status] == 1
    assert report["counts"]["expected_rows"] == 2
    assert report["rank_metrics"]["score_coverage"]["value"] == .5
    assert report["rank_metrics"]["mrr_all_work_operational"]["denominator"] == 1
    assert report["rank_metrics"]["gold_present_top1_all_terminals"]["denominator"] == 1
    assert report["rows"][0]["action"] == "UNAVAILABLE"
    assert report["calibration_evaluation"]["status"] == "NOT_EVALUABLE"


@pytest.mark.parametrize("result,reason", [(None, "PIPELINE_NOT_EXECUTED"),
    (SimpleNamespace(), "RECEIPT_NOT_AVAILABLE"),
    (SimpleNamespace(_candidate_reranker_shadow={"broken": True}), "INVALID_OR_OVERSIZED_RECEIPT")])
def test_real_exporter_not_executed_is_unobserved_not_complete(bundle, artifact, result, reason):
    args = inputs(bundle, artifact)
    binding = args["observations"][0]["receipt"]["binding"]
    receipt = export_candidate_reranker_fields(result, bundle["scorer"], binding=binding)["candidate_reranker_shadow"]
    assert receipt["reason_codes"] == [reason]
    args["observations"][0]["receipt"] = receipt
    args["frozen_rows"] = args["frozen_rows"][1:]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    row = report["rows"][0]
    assert row["receipt_sha256"] == receipt["receipt_sha256"]
    assert row["source_terminal"] == "NOT_AVAILABLE" and row["generation_status"] == "UNKNOWN"
    assert row["gold_present"] is None and "GENERATION_NOT_OBSERVED" in row["binding_limits"]
    assert report["counts"]["observed_rows"] == 2


@pytest.mark.parametrize("through_export", [False, True])
def test_actual_unavailable_scorer_template_keeps_own_hash_and_manifest_pin(bundle, artifact, through_export):
    args = inputs(bundle, artifact)
    scorer = adapter.unavailable_scorer("MODEL_UNAVAILABLE", expected_sha256=args["scorer_summary"]["model_manifest_sha256"])
    receipt = scorer.score(args["expected_rows"][0]["frozen_view"])
    binding = args["observations"][0]["receipt"]["binding"]
    if through_export:
        receipt = export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt),
            scorer, binding=binding)["candidate_reranker_shadow"]
    else:
        receipt["binding"] = binding
    args["observations"][0]["receipt"] = receipt
    args["frozen_rows"] = args["frozen_rows"][1:]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    row = report["rows"][0]
    assert row["source_terminal"] == "UNAVAILABLE_MODEL"
    assert row["receipt_sha256"] == receipt["receipt_sha256"]
    assert row["observed_model_binding"]["scorer_sha256"] == scorer.summary()["scorer_sha256"]
    assert row["observed_model_binding"]["scorer_sha256"] != args["scorer_summary"]["scorer_sha256"]
    assert row["observed_model_binding"]["actual_model_available"] is False
    assert "MODEL_NOT_LOADED_MANIFEST_PIN_ONLY" in row["binding_limits"]
    assert report["counts"]["observed_rows"] == 2 and row["action"] == "UNAVAILABLE"


@pytest.mark.parametrize("case,expected_status", [("UNKNOWN", "NOT_SCORED_GENERATION_UNKNOWN"),
    ("TRUNCATED", "NOT_SCORED_GENERATION_TRUNCATED"), ("EMPTY", "EMPTY_CANDIDATE_SET")])
@pytest.mark.parametrize("through_export", [False, True])
def test_real_unavailable_scorer_preemptive_terminals_keep_all_rows(bundle, artifact, case, expected_status, through_export):
    args = inputs(bundle, artifact)
    view = args["expected_rows"][0]["frozen_view"]
    if case == "EMPTY":
        view["candidates"] = []
        args["expected_rows"][0]["candidate_text_bindings"] = []
    else:
        view["generation_status"] = case
    recap(args, 0)
    scorer = adapter.unavailable_scorer("MODEL_UNAVAILABLE", expected_sha256=args["scorer_summary"]["model_manifest_sha256"])
    receipt = scorer.score(view)
    assert receipt["status"] == expected_status
    binding = args["observations"][0]["receipt"]["binding"]
    if through_export:
        receipt = export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt),
            scorer, binding=binding)["candidate_reranker_shadow"]
    else:
        receipt["binding"] = binding
    args["observations"][0]["receipt"] = receipt
    args["frozen_rows"] = args["frozen_rows"][1:]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    row = report["rows"][0]
    assert row["source_terminal"] == expected_status
    assert row["observed_model_binding"]["actual_model_available"] is False
    assert row["observed_model_binding"]["scorer_sha256"] == scorer.summary()["scorer_sha256"]
    assert report["counts"]["observed_rows"] == 2
    assert report["rank_metrics"]["score_coverage"]["value"] == .5
    assert row["action"] == ("ABSTAIN" if case == "EMPTY" else "UNAVAILABLE")
    assert row["calibration_shadow"] is None


@pytest.fixture(scope="module")
def runtime_bundle(tmp_path_factory):
    from candidate_calibration_runtime_fixtures import build_runtime_calibration_fixture
    result = build_runtime_calibration_fixture(tmp_path_factory.mktemp("nil-evaluation-real-runtime"))
    common_keys = ("training_manifest", "expected_training_manifest_sha256", "source_payloads", "evidence_payloads",
        "scorer_summary", "expected_scorer_summary_sha256", "calibration_manifest", "expected_calibration_manifest_sha256")
    return {**result, "common_kwargs": {key: result["frozen_args"][0][key] for key in common_keys}}


def runtime_unavailable_inputs(runtime_bundle):
    from src.llm_batch.runtime.candidate_reranker import _source_view, observe_candidate_reranker
    from src.llm_batch.grounding.candidate_reranker_roles import observe_preselection_roles
    args = inputs(runtime_bundle, runtime_bundle["artifact"])
    original = runtime_bundle["frozen_runtime_rows"][0]["post"]
    # 관측 API의 source-view 계약을 dataset의 문자열 ID로 직접 실행한다.
    # expert_main의 정수 PostInput을 변조하거나 receipt ID를 사후 치환하지 않는다.
    post = SimpleNamespace(post_id=args["expected_rows"][0]["frozen_view"]["post_id"],
        title=original.title, content_blocks=deepcopy(original.content_blocks), comments=deepcopy(original.comments))
    r2 = runtime_bundle["retrieval_observer"]
    source = _source_view(post)
    r2_receipt = r2.observe(source)
    assert r2_receipt["status"] == "OK"
    expected_view, metadata = observe_preselection_roles(adapter.build_frozen_view(source, r2_receipt))
    scorer = adapter.unavailable_scorer("MODEL_UNAVAILABLE", expected_sha256=args["scorer_summary"]["model_manifest_sha256"])
    raw = observe_candidate_reranker(scorer, post, r2_receipt, r2)
    assert raw["status"] == "UNAVAILABLE_MODEL" and raw["preselection_role_producer"] == metadata
    binding = args["observations"][0]["receipt"]["binding"]
    receipt = export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=raw), scorer,
        binding=binding)["candidate_reranker_shadow"]
    assert receipt["status"] == "UNAVAILABLE_MODEL"
    args["expected_rows"][0]["frozen_view"] = expected_view
    args["observations"][0]["receipt"] = receipt
    recap(args, 0)
    args["frozen_rows"] = args["frozen_rows"][1:]
    return args, receipt


def test_real_r2_runtime_roles_unavailable_scorer_and_export_preserve_denominator(runtime_bundle, monkeypatch):
    args, receipt = runtime_unavailable_inputs(runtime_bundle)
    assert receipt["preselection_role_producer"]["status"] == "OBSERVED"
    monkeypatch.setattr(adapter.FrozenCandidateRerankerShadow, "score", lambda *a, **k: pytest.fail("평가 중 scorer 호출 금지"))
    report = evaluation.evaluate_frozen_nil_scores(**args)
    row = report["rows"][0]
    assert row["source_terminal"] == "UNAVAILABLE_MODEL" and row["receipt_sha256"] == receipt["receipt_sha256"]
    assert row["observed_model_binding"]["scorer_sha256"] == receipt["scorer_sha256"]
    assert row["calibration_shadow"] is None and report["counts"]["observed_rows"] == 2


@pytest.mark.parametrize("field", ["frozen_view_sha256", "policy_sha256", "counts"])
def test_resealed_runtime_unavailable_role_metadata_does_not_bypass_source_binding(runtime_bundle, field):
    args, receipt = runtime_unavailable_inputs(runtime_bundle)
    metadata = receipt["preselection_role_producer"]
    if field == "counts":
        metadata["counts"]["observations"] += 1
    else:
        metadata[field] = "f" * 64
    reseal(receipt)
    with pytest.raises(ValueError):
        evaluation.evaluate_frozen_nil_scores(**args)


def test_unavailable_preemptive_branch_order_cannot_be_relabelled(bundle, artifact):
    args = inputs(bundle, artifact)
    view = args["expected_rows"][0]["frozen_view"]
    view["generation_status"] = "UNKNOWN"
    recap(args, 0)
    scorer = adapter.unavailable_scorer("MODEL_UNAVAILABLE", expected_sha256=args["scorer_summary"]["model_manifest_sha256"])
    receipt = scorer.score(view)
    receipt.update(status="UNAVAILABLE_MODEL", reason_codes=["MODEL_UNAVAILABLE"],
        binding=args["observations"][0]["receipt"]["binding"])
    args["observations"][0]["receipt"] = reseal(receipt)
    args["frozen_rows"] = []
    with pytest.raises(ValueError, match="UNAVAILABLE_MODEL_BRANCH_MISMATCH"):
        evaluation.evaluate_frozen_nil_scores(**args)


@pytest.mark.parametrize("field", ["model_manifest_sha256", "scorer_sha256", "feature_schema_sha256"])
def test_unavailable_template_does_not_excuse_known_hash_conflicts(bundle, artifact, field):
    args = inputs(bundle, artifact)
    receipt = adapter.unavailable_scorer("MODEL_UNAVAILABLE",
        expected_sha256=args["scorer_summary"]["model_manifest_sha256"]).score(args["expected_rows"][0]["frozen_view"])
    receipt["binding"] = args["observations"][0]["receipt"]["binding"]
    receipt[field] = "f" * 64
    args["observations"][0]["receipt"] = reseal(receipt)
    args["frozen_rows"] = []
    with pytest.raises(ValueError, match="UNAVAILABLE_MODEL_TEMPLATE"):
        evaluation.evaluate_frozen_nil_scores(**args)


@pytest.mark.parametrize("key,value", [("generation_sha256", "a" * 64), ("query_sha256", "a" * 64),
    ("generation_status", "COMPLETE"), ("nil_score", 0), ("public_apply", True)])
def test_resealed_not_executed_sentinel_cannot_hide_observation_or_authority(bundle, artifact, key, value):
    args = inputs(bundle, artifact)
    receipt = export_candidate_reranker_fields(None, bundle["scorer"],
        binding=args["observations"][0]["receipt"]["binding"])["candidate_reranker_shadow"]
    receipt[key] = value
    args["observations"][0]["receipt"] = reseal(receipt)
    args["frozen_rows"] = []
    with pytest.raises(ValueError):
        evaluation.evaluate_frozen_nil_scores(**args)


@pytest.mark.parametrize("generation,status", [("TRUNCATED", "NOT_SCORED_GENERATION_TRUNCATED"),
                                                ("UNKNOWN", "NOT_SCORED_GENERATION_UNKNOWN")])
def test_real_scorer_generation_terminal_stays_in_denominator(bundle, artifact, generation, status):
    args = inputs(bundle, artifact)
    args["expected_rows"][0]["frozen_view"]["generation_status"] = generation
    rescore(args, bundle, 0)
    args["frozen_rows"] = args["frozen_rows"][1:]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["rows"][0]["source_terminal"] == status
    assert report["rows"][0]["gold_present"] is None
    assert report["counts"]["expected_rows"] == 2


def test_real_empty_generation_abstains_without_becoming_nil(bundle, artifact):
    args = inputs(bundle, artifact)
    args["expected_rows"][0]["frozen_view"]["candidates"] = []
    args["expected_rows"][0]["candidate_text_bindings"] = []
    rescore(args, bundle, 0)
    args["frozen_rows"] = args["frozen_rows"][1:]
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["rows"][0]["source_terminal"] == "EMPTY_CANDIDATE_SET"
    assert report["rows"][0]["action"] == "ABSTAIN"
    assert report["rows"][0]["truth_kind"] == "CANDIDATE"
    assert report["rank_metrics"]["candidate_recall"]["value"] == 0


def test_gold_missing_score_remains_zero_mrr_and_excluded_from_conditional_accuracy(bundle, artifact):
    args = inputs(bundle, artifact)
    exp = args["expected_rows"][0]
    assignment = next(r for r in args["training_manifest"]["rows"] if r["assignment"]["example_id"] == exp["example_id"])
    gold = assignment["assignment"]["truth_label"]
    corpus = next(b["corpus_candidate_id"] for b in assignment["r2_id_bridges"] if b["candidate_ids"] == [gold])
    exp["frozen_view"]["candidates"] = [c for c in exp["frozen_view"]["candidates"] if c["candidate_id"] != corpus]
    exp["candidate_text_bindings"] = [c for c in exp["candidate_text_bindings"] if c["candidate_id"] != corpus]
    rescore(args, bundle, 0)
    rebind_graph(args, 0)
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["rows"][0]["gold_present"] is False
    assert report["rank_metrics"]["mrr_scored_work"]["value"] == 0
    assert report["rank_metrics"]["gold_present_top1_accuracy"]["denominator"] == 0
    assert report["rank_metrics"]["score_coverage"]["denominator"] == 2
    assert "INCOMPLETE_EVENT_SPACE" in report["rows"][0]["calibration_reason_codes"]
    assert "GOLD_CANDIDATE_NOT_RETRIEVED" in report["rows"][0]["calibration_reason_codes"]


def test_highest_nil_with_abstain_does_not_count_as_assert_nil(bundle, artifact):
    args = inputs(bundle, artifact)
    for i, obs in enumerate(args["observations"]):
        # 구형 선택/분모 계약만의 raw-logit 합성 반례. CLI에서는 실제 score 재생도 별도 검산한다.
        receipt = obs["receipt"]
        for ranked in receipt["ranked_candidates"]:
            ranked["score"] = 0.0
        receipt["ranked_candidates"].sort(key=lambda r: r["candidate_id"])
        receipt["nil_score"] = .01
        for event in receipt["event_logits"]:
            event["score"] = .01 if event.get("label") == "__NIL__" else 0.0
        reseal(receipt)
        rebind_graph(args, i)
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert all(r["calibration_shadow"]["selected_label"] == "__NIL__" for r in report["rows"])
    assert all(r["action"] == "ABSTAIN" for r in report["rows"])
    assert report["counts"]["shadow_actions"].get("ASSERT_NIL", 0) == 0
    assert report["calibration_evaluation"]["metrics"]["nil_precision"] is None


@pytest.mark.parametrize("field", ["expected_rows", "observations", "frozen_rows"])
@pytest.mark.parametrize("operation", ["reverse", "duplicate"])
def test_order_and_duplicate_ids_fail_closed(bundle, artifact, field, operation):
    args = inputs(bundle, artifact)
    args[field] = list(reversed(args[field])) if operation == "reverse" else [args[field][0], args[field][0]]
    with pytest.raises(ValueError):
        evaluation.evaluate_frozen_nil_scores(**args)


@pytest.mark.parametrize("key,value", [("nil_score", True), ("model_sha256", "f" * 64),
    ("training_split_manifest_sha256", "f" * 64), ("candidate_ranker_model_sha256", "f" * 64),
    ("actual_model_available", False), ("nil_head_available", False), ("data_kind", "SOURCE_BACKED"),
    ("publication_authority", True), ("nil_probability", .9)])
@pytest.mark.parametrize("terminal", [False, True])
def test_resealed_model_nil_and_authority_tampering_fails_all_statuses(bundle, artifact, key, value, terminal):
    args = inputs(bundle, artifact)
    receipt = args["observations"][0]["receipt"]
    if terminal:
        receipt.update(status="ERROR", ranked_candidates=[], nil_score=None, event_logits=[])
    receipt[key] = value
    reseal(receipt)
    args["frozen_rows"] = []
    with pytest.raises(ValueError):
        evaluation.evaluate_frozen_nil_scores(**args)


@pytest.mark.parametrize("mutation", ["event_order", "score", "typed_post", "capture", "source", "graph_raw", "graph_sha"])
def test_event_source_capture_and_graph_tampering(bundle, artifact, mutation):
    args = inputs(bundle, artifact)
    receipt = args["observations"][0]["receipt"]
    if mutation == "event_order":
        receipt["event_logits"].reverse()
        reseal(receipt)
    elif mutation == "score":
        receipt["ranked_candidates"][0]["score"] += 1
        reseal(receipt)
    elif mutation == "typed_post":
        receipt["post_id"] = 123
        reseal(receipt)
    elif mutation == "capture":
        args["expected_rows"][0]["capture_sha256"] = "f" * 64
    elif mutation == "source":
        key = next(iter(args["source_payloads"]))
        args["source_payloads"][key] += b"tamper"
    elif mutation == "graph_raw":
        args["frozen_rows"][0]["raw_receipt"]["nil_score"] += 1
        reseal(args["frozen_rows"][0]["raw_receipt"])
    else:
        args["frozen_rows"][0]["source_binding_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        evaluation.evaluate_frozen_nil_scores(**args)


@pytest.mark.parametrize("field", ["expected_training_manifest_sha256", "expected_calibration_manifest_sha256",
    "expected_scorer_summary_sha256", "expected_policy_sha256", "expected_artifact_sha256"])
def test_explicit_pins_are_not_optional_when_supplied(bundle, artifact, field):
    args = inputs(bundle, artifact)
    args[field] = "f" * 64
    with pytest.raises(ValueError):
        evaluation.evaluate_frozen_nil_scores(**args)


def test_frozen_actual_is_explicitly_not_supported_without_actual_readback(bundle, artifact):
    report = evaluation.evaluate_frozen_nil_scores(**inputs(bundle, artifact), evidence_mode="FROZEN_ACTUAL")
    assert report["counts"]["expected_rows"] == 2
    assert report["rank_metrics"]["score_coverage"]["value"] == 1
    assert "ACTUAL_READBACK_AND_BASELINE_NOT_SUPPORTED" in report["reason_codes"]
    assert report["calibration_evaluation"]["metrics"]["multiclass_brier"] is None


def rewrite_manifest_identity(args):
    args["training_manifest"] = split.seal_manifest(args["training_manifest"])
    manifest = args["training_manifest"]
    args["expected_training_manifest_sha256"] = manifest["manifest_sha256"]
    old = args["calibration_manifest"]
    cal = legacy.CalibrationSplitManifest.create(assignments=[legacy.CalibrationSplitAssignment(**a)
        for a in split.calibration_assignments(manifest)], source_label_ledger_sha256=old.source_label_ledger_sha256,
        assignment_seed_sha256=old.assignment_seed_sha256)
    args["calibration_manifest"] = cal
    args["expected_calibration_manifest_sha256"] = cal.manifest_sha256
    args["scorer_summary"]["training_split_manifest_sha256"] = manifest["manifest_sha256"]
    args["scorer_summary"]["data_kind"] = manifest["data_kind"]
    args["expected_scorer_summary_sha256"] = evaluation.canonical_sha256(args["scorer_summary"])
    for obs in args["observations"]:
        obs["receipt"]["training_split_manifest_sha256"] = manifest["manifest_sha256"]
        obs["receipt"]["data_kind"] = manifest["data_kind"]
        reseal(obs["receipt"])
    args["frozen_rows"] = []


def test_unjudged_is_retained_and_never_scored_as_nil(bundle):
    args = inputs(bundle, None)
    row = next(r for r in args["training_manifest"]["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT")
    row["assignment"].update(truth_kind="UNJUDGED", truth_label=None, matched_candidate_ids=[],
        binding_status="NOT_APPLICABLE", gold_work_fingerprint=None)
    row["label_provenance"]["grade"] = "UNJUDGED"
    rewrite_manifest_identity(args)
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["counts"]["truth_kinds"] == {"NIL": 1, "UNJUDGED": 1}
    assert report["counts"]["label_grades"]["UNJUDGED"] == 1
    assert report["rank_metrics"]["mrr_scored_work"]["denominator"] == 0
    assert report["counts"]["expected_rows"] == 2


def test_source_backed_declarations_do_not_gain_actual_acceptance(bundle):
    # 이 반례는 입력 enum·선언 결속 경계만 시험한다. 실제 source-backed 학습으로 보고하지 않는다.
    args = inputs(bundle, None)
    args["training_manifest"]["data_kind"] = "SOURCE_BACKED"
    for source in args["training_manifest"]["sources"]:
        source["rights_status"] = "UNKNOWN"
    for row in args["training_manifest"]["rows"]:
        row["label_provenance"]["grade"] = "MODEL_REFERENCE"
        for role in row["role_mentions"]:
            role["provenance"]["grade"] = "MODEL_REFERENCE"
    rewrite_manifest_identity(args)
    report = evaluation.evaluate_frozen_nil_scores(**args)
    assert report["data_kind"] == "SOURCE_BACKED" and report["rank_metrics"]["score_coverage"]["denominator"] == 2
    assert report["actual_quality_evaluated"] is report["quality_acceptance_claimed"] is False
    assert "ACTUAL_READBACK_AND_BASELINE_NOT_SUPPORTED" in report["reason_codes"]


def test_row_bound_rejects_before_graph_or_fixture_processing(bundle, artifact):
    args = inputs(bundle, artifact)
    args["expected_rows"] *= evaluation.MAX_ROWS
    args["observations"] *= evaluation.MAX_ROWS
    with pytest.raises(ValueError, match="ROW_LIMIT"):
        evaluation.evaluate_frozen_nil_scores(**args)


def test_v1_pairwise_evaluator_contract_still_operates():
    from test_candidate_reranker_evaluation import dataset, evaluate
    report = evaluate(dataset())
    assert report["schema_version"] == "candidate_reranker_score_evaluation_v1"
    assert report["model_binding"]["backend"] == "PAIRWISE_LINEAR_V1"


def test_pairwise_summary_cannot_bypass_nil_gate(bundle):
    args = inputs(bundle, None)
    args["scorer_summary"]["backend"] = "PAIRWISE_LINEAR_V1"
    args["expected_scorer_summary_sha256"] = evaluation.canonical_sha256(args["scorer_summary"])
    with pytest.raises(ValueError, match="NIL_LEARNED_MODEL_REQUIRED"):
        evaluation.evaluate_frozen_nil_scores(**args)
