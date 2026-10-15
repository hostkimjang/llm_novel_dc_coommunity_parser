"""새 합성 원문·라벨만 사용한 evaluator 계약 시험. 실제 데이터 품질 주장이 아니다."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from src.llm_batch.grounding import reranker_training_split as split
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.measurement import candidate_reranker_evaluation as evaluation
from src.llm_batch.runtime.candidate_reranker import export_candidate_reranker_fields


def raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def seal_receipt(receipt):
    receipt["receipt_sha256"] = evaluation.canonical_sha256({key: value for key, value in receipt.items()
        if key not in {"receipt_sha256", "latency_ms", "binding"}})
    return receipt


def dataset(frozen_specs=None):
    """각 split의 모든 work/source/lineage가 분리된 새 합성 fixture."""
    frozen_specs = [{}] if frozen_specs is None else frozen_specs
    specs = [("TRAIN", {}), ("DEV", {}), ("CALIBRATION", {})]
    specs += [("FROZEN_HOLDOUT", spec) for spec in frozen_specs]
    sources, rows, payloads, evidence, views, text_bindings, row_specs = [], [], {}, {}, {}, {}, {}
    for index, (partition, spec) in enumerate(specs):
        sid, example, post = f"source-{index}", f"example-{index}", str(100 + index)
        tokens = [f"주작품{index}", f"비교작{index}", f"언급작{index}"]
        text = " 그리고 ".join(tokens)
        encoded = text.encode()
        payloads[sid] = encoded
        sources.append({"source_id": sid, "payload_sha256": sha(encoded), "source_group_id": f"group-{index}",
            "lineage_root_id": f"lineage-{index}", "rights_status": "SYNTHETIC_FIXTURE"})
        annotation = raw({"synthetic_annotation": index, "label": spec.get("truth", "CANDIDATE")})
        annotation_sha = sha(annotation)
        evidence[annotation_sha] = annotation
        original = {"source_id": sid, "raw_path": "/content", "utf8_byte_span_start": 0,
                    "utf8_byte_span_end": len(encoded), "text": text, "span_sha256": sha(encoded)}
        exposures, bridges, mentions, candidates, bindings = [], [], [], [], []
        for pos, token in enumerate(tokens):
            cid, corpus = f"candidate-{index}-{pos}", f"corpus-{index}-{pos}"
            positive = pos == 0 and spec.get("truth", "CANDIDATE") == "CANDIDATE"
            exposures.append({"candidate_id": cid, "corpus_candidate_id": corpus,
                "polarity": "POSITIVE" if positive else "NEGATIVE", "work_id": f"work-{index}-{pos}",
                "edition_id": f"edition-{index}-{pos}", "media_type": "WEB_NOVEL",
                "alias_family_ids": [f"family-{index}-{pos}"], "source_ids": [sid]})
            bridges.append({"corpus_candidate_id": corpus, "status": "UNIQUE", "candidate_ids": [cid],
                            "provenance_sha256": annotation_sha})
            byte_start, char_start = encoded.index(token.encode()), text.index(token)
            span = {**original, "utf8_byte_span_start": byte_start,
                "utf8_byte_span_end": byte_start + len(token.encode()), "text": token, "span_sha256": sha(token.encode())}
            role = ["PRIMARY", "COMPARISON", "MENTIONED"][pos]
            mentions.append({"candidate_id": cid, "source_span": span, "roles": [role], "provenance": {
                "grade": "SYNTHETIC_FIXTURE", "artifact_sha256": annotation_sha,
                "reviewer": "synthetic reviewer", "scope": "MENTION_ROLE"}})
            candidates.append({"candidate_id": corpus, "titles": [token], "urls": [], "aliases": [],
                "option_kind": "WORK_CANDIDATE", "event_eligible": True, "identity_conflict": False,
                "negative_evidence": [], "role_observations": [{"role": role, "raw_path": "/content",
                "start": char_start, "end": char_start + len(token), "text_sha256": sha(token.encode())}]})
            bindings.append({"candidate_id": corpus, "titles": [span], "aliases": []})
        truth = spec.get("truth", "CANDIDATE")
        assignment = {"example_id": example, "post_id": post, "split_group_id": f"split-group-{index}",
            "content_fingerprint": split.canonical_sha256([original]),
            "source_group_fingerprint": split.canonical_sha256([f"group-{index}"]), "split": partition,
            "truth_kind": truth, "truth_label": exposures[0]["candidate_id"] if truth == "CANDIDATE" else "__NIL__" if truth == "NIL" else None,
            "label_provenance_sha256": annotation_sha, "candidate_set_fingerprint": split.canonical_sha256(exposures),
            "gold_work_fingerprint": split.canonical_sha256(exposures[0]["work_id"]) if truth == "CANDIDATE" else None,
            "binding_status": "UNIQUE" if truth == "CANDIDATE" else "NOT_APPLICABLE",
            "matched_candidate_ids": [exposures[0]["candidate_id"]] if truth == "CANDIDATE" else []}
        rows.append({"assignment": assignment, "binding": {"run_id": "synthetic-run", "attempt_id": f"attempt-{index}",
                    "input_index": index + 1}, "source_ids": [sid], "source_spans": [original],
            "exposures": exposures, "r2_id_bridges": bridges, "role_mentions": mentions,
            "label_provenance": {"grade": "SYNTHETIC_FIXTURE", "artifact_sha256": annotation_sha,
                                 "reviewer": "synthetic reviewer", "scope": "WORK_IDENTITY"}})
        keep = spec.get("keep", [0, 1, 2])
        views[example] = {"schema_version": adapter.VIEW_SCHEMA, "stage": "PRE_SELECTION", "post_id": post,
            "source_view": {"schema_version": adapter.SOURCE_SCHEMA, "post_id": post,
                            "fragments": [{"raw_path": "/content", "kind": "BODY", "text": text}]},
            "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": sha(f"generation-{index}".encode()),
            "candidate_set_fingerprint": None, "generation_status": spec.get("generation", "COMPLETE"),
            "candidates": [candidates[pos] for pos in keep]}
        text_bindings[example] = [bindings[pos] for pos in keep]
        row_specs[example] = spec
    manifest = split.seal_manifest({"schema_version": split.SCHEMA_VERSION, "data_kind": "SYNTHETIC_FIXTURE",
        "split_policy_version": split.POLICY_VERSION, "sources": sources, "rows": rows})
    model = {field: sha(field.encode()) for field in evaluation.HASH_FIELDS}
    model.update(backend="PAIRWISE_LINEAR_V1", data_kind="SYNTHETIC_FIXTURE",
                 training_status="TRAINED_PAIRWISE_LINEAR", actual_model_available=True,
                 training_split_manifest_sha256=manifest["manifest_sha256"])
    bundle = {"manifest": manifest, "source": payloads, "evidence": evidence, "views": views,
              "text_bindings": text_bindings, "specs": row_specs, "model": model}
    for row in rows:
        capture(bundle, row)
    return bundle


def capture(bundle, row):
    assignment = row["assignment"]
    example = assignment["example_id"]
    value = {"schema_version": "reranker_preselection_capture_v1", "stage": "PRE_SELECTION",
        "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD", "example_id": example,
        "post_id": assignment["post_id"], "binding": row["binding"],
        "source_spans_sha256": evaluation.canonical_sha256(row["source_spans"]),
        "candidate_set_fingerprint": assignment["candidate_set_fingerprint"],
        "frozen_view_sha256": evaluation.canonical_sha256(bundle["views"][example]),
        "candidate_text_bindings_sha256": evaluation.canonical_sha256(bundle["text_bindings"][example])}
    encoded = raw(value)
    digest = sha(encoded)
    bundle["evidence"][digest] = encoded
    bundle.setdefault("captures", {})[example] = digest


def evaluation_inputs(bundle, partition):
    expected, observations = [], []
    for row in bundle["manifest"]["rows"]:
        if row["assignment"]["split"] != partition:
            continue
        assignment = row["assignment"]
        example = assignment["example_id"]
        view, spec = bundle["views"][example], bundle["specs"][example]
        expected.append({"example_id": example, "publication_scope_id": "synthetic-scope",
            "frozen_view": deepcopy(view), "candidate_text_bindings": deepcopy(bundle["text_bindings"][example]),
            "capture_sha256": bundle["captures"][example]})
        status = spec.get("status", "SCORED_LEARNED")
        values = spec.get("scores", [3.0, 1.0, 0.0])
        ranked = [{"candidate_id": candidate["candidate_id"], "score": values[int(candidate["candidate_id"].split("-")[-1])]}
                  for candidate in view["candidates"]] if status == "SCORED_LEARNED" else []
        ranked.sort(key=lambda item: (-item["score"], item["candidate_id"]))
        receipt = {**bundle["model"], "schema_version": adapter.RECEIPT_SCHEMA, "mode": "SHADOW", "status": status,
            "receipt_digest_scope": adapter.DIGEST_SCOPE, "post_id": assignment["post_id"],
            "query_sha256": evaluation.canonical_sha256(view["source_view"]),
            "input_sha256": evaluation.canonical_sha256(view), "candidate_view_sha256": evaluation.canonical_sha256(view["candidates"]),
            "generation_sha256": view["generation_sha256"], "candidate_set_fingerprint": view["candidate_set_fingerprint"],
            "candidate_namespace": view["candidate_namespace"], "generation_status": view["generation_status"],
            "frozen_candidate_ids": [item["candidate_id"] for item in view["candidates"]], "ranked_candidates": ranked,
            "candidate_observations": [{"candidate_id": item["candidate_id"], "role_observations": item["role_observations"]}
                                       for item in view["candidates"]],
            "publication_authority": False, "central_db_write": False, "public_apply": False,
            "probability_status": "NOT_AVAILABLE_UNCALIBRATED", "selected_candidate_id": None,
            "nil_probability": None, "operational_effect": "NONE_SHADOW_ONLY",
            "binding": {**row["binding"], "post_id": assignment["post_id"],
                        "publication_scope_id": "synthetic-scope", "scope": "ATTEMPT_LOCAL_OBSERVATION"}}
        observations.append({"example_id": example, "receipt": seal_receipt(receipt)})
    return {"split_manifest": bundle["manifest"], "source_payloads": bundle["source"],
            "evidence_payloads": bundle["evidence"], "expected_rows": expected, "observations": observations,
            "scorer_summary": bundle["model"]}


def fit(bundle, **overrides):
    args = evaluation_inputs(bundle, "CALIBRATION")
    args.update(score_thresholds=[2.0], margin_thresholds=[0.5], max_empirical_risk=0.0)
    args.update(overrides)
    return evaluation.fit_calibration_thresholds(**args)


def evaluate(bundle, policy=None, **overrides):
    policy = fit(bundle)["policy"] if policy is None else policy
    args = evaluation_inputs(bundle, "FROZEN_HOLDOUT")
    args.update(threshold_policy=policy, expected_policy_sha256=policy["policy_sha256"])
    args.update(overrides)
    return evaluation.evaluate_frozen_scores(**args)


def test_cal_freezes_policy_and_frozen_report_is_deterministic_without_input_mutation():
    bundle = dataset()
    before = deepcopy(bundle)
    calibrated = fit(bundle)
    assert calibrated["status"] == "CAL_POLICY_FROZEN"
    assert calibrated["policy"]["method"] == "CAL_ONLY_RAW_SCORE_MARGIN_V1"
    report = evaluate(bundle, calibrated["policy"])
    assert report["status"] == "FROZEN_SCORE_EVALUATED" and report["thresholds_refit_on_frozen"] is False
    assert report["metrics"]["mrr_scored_work"]["value"] == 1
    assert report["metrics"]["selective_risk"]["value"] == 0
    assert report["evidence_scope"] == "SYNTHETIC_ONLY" and not report["quality_acceptance_claimed"]
    assert report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert all(report[key] is False for key in ("publication_authority", "public_apply", "central_db_write"))
    assert bundle == before and evaluate(bundle, calibrated["policy"]) == report
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    assert evaluation.canonical_sha256(body) == report["report_sha256"]


def test_metrics_preserve_all_terminals_gold_present_condition_and_nil_vs_abstain():
    bundle = dataset([{}, {"scores": [1, 3, 0]}, {"keep": [1, 2], "scores": [0, 3, 1]},
        {"status": "ERROR"}, {"scores": [3, 2.9, 0]}, {"truth": "NIL"},
        {"truth": "NIL", "keep": [], "status": "EMPTY_CANDIDATE_SET"}])
    report = evaluate(bundle)
    metrics = report["metrics"]
    assert report["counts"]["expected_rows"] == report["counts"]["observed_rows"] == 7
    assert metrics["mrr_scored_work"]["value"] == pytest.approx(2.5 / 4)
    assert metrics["mrr_all_work_operational"]["value"] == pytest.approx(2.5 / 5)
    assert metrics["gold_present_top1_accuracy"]["value"] == pytest.approx(2 / 3)
    assert metrics["gold_present_selection_accuracy"]["value"] == pytest.approx(1 / 4)
    assert metrics["decision_coverage"]["value"] == pytest.approx(4 / 7)
    assert metrics["score_coverage"]["value"] == pytest.approx(5 / 7)
    assert metrics["selective_risk"]["value"] == pytest.approx(3 / 4)
    assert report["counts"]["actions"] == {"ABSTAIN": 2, "SELECT_CANDIDATE": 4, "UNAVAILABLE": 1}
    assert metrics["nil"]["truth_count"] == 2 and metrics["nil"]["candidate_selected_on_nil_truth"] == 1
    assert metrics["nil"]["predicted_nil"] == 0 and metrics["nil"]["precision"] is metrics["nil"]["recall"] is None
    assert all(row["action"] != "NIL" for row in report["rows"])


def test_generation_unknown_and_truncated_are_not_rank_quality_or_true_nil():
    bundle = dataset([{"generation": value, "status": "NOT_SCORED_GENERATION_" + value}
                      for value in ("UNKNOWN", "TRUNCATED")])
    report = evaluate(bundle)
    assert report["metrics"]["mrr_scored_work"]["value"] is None
    assert report["metrics"]["candidate_recall"]["value"] is None
    assert report["metrics"]["mrr_all_work_operational"]["value"] == 0
    assert report["metrics"]["decision_coverage"]["value"] == 0
    assert report["metrics"]["selective_risk"]["value"] is None
    assert all(row["action"] == "UNAVAILABLE" and row["gold_present"] is None for row in report["rows"])


def test_single_candidate_margin_is_unknown_and_abstains_without_becoming_nil():
    report = evaluate(dataset([{"keep": [0]}]))
    assert report["rows"][0]["margin"] is None
    assert report["rows"][0]["action"] == "ABSTAIN"
    assert report["metrics"]["gold_present_top1_accuracy"]["value"] == 1
    assert report["metrics"]["selective_risk"]["value"] is None


def test_raw_scores_outside_probability_range_are_valid_but_never_probabilities():
    report = evaluate(dataset([{"scores": [19, -3, -100]}]))
    assert report["rows"][0]["top_score"] == 19 and report["rows"][0]["margin"] == 22
    assert report["probability_status"] == "NOT_AVAILABLE_UNCALIBRATED"


@pytest.mark.parametrize("side,change", [("expected_rows", "drop"), ("observations", "drop"),
    ("expected_rows", "duplicate"), ("observations", "duplicate"),
    ("expected_rows", "reverse"), ("observations", "reverse")])
def test_external_expected_universe_and_observations_must_include_exact_ordered_split(side, change):
    bundle = dataset([{}, {}])
    inputs = evaluation_inputs(bundle, "FROZEN_HOLDOUT")
    if change == "drop":
        inputs[side].pop()
    elif change == "duplicate":
        inputs[side][1] = deepcopy(inputs[side][0])
    else:
        inputs[side].reverse()
    policy = fit(bundle)["policy"]
    with pytest.raises(evaluation.RerankerEvaluationError, match="UNIVERSE_ORDER_OR_SET_MISMATCH"):
        evaluation.evaluate_frozen_scores(**inputs, threshold_policy=policy, expected_policy_sha256=policy["policy_sha256"])


@pytest.mark.parametrize("field", list(evaluation.HASH_FIELDS))
def test_receipt_cannot_switch_fixed_model_even_after_self_reseal(field):
    bundle = dataset()
    inputs = evaluation_inputs(bundle, "FROZEN_HOLDOUT")
    receipt = inputs["observations"][0]["receipt"]
    receipt[field] = "a" * 64
    seal_receipt(receipt)
    with pytest.raises(evaluation.RerankerEvaluationError, match="MODEL_"):
        evaluate(bundle, observations=inputs["observations"])


@pytest.mark.parametrize("field,value", [("post_id", 103), ("attempt_id", "foreign"),
    ("input_index", True), ("publication_scope_id", "foreign"), ("scope", "OTHER_SCOPE")])
def test_storage_binding_is_independently_checked_outside_receipt_digest(field, value):
    bundle = dataset()
    observations = evaluation_inputs(bundle, "FROZEN_HOLDOUT")["observations"]
    observations[0]["receipt"]["binding"][field] = value
    with pytest.raises(evaluation.RerankerEvaluationError, match="RECEIPT_STORAGE_BINDING"):
        evaluate(bundle, observations=observations)


@pytest.mark.parametrize("field", ["query_sha256", "input_sha256", "candidate_view_sha256", "generation_sha256"])
def test_error_receipt_does_not_hide_known_source_fingerprint_contradiction(field):
    bundle = dataset([{"status": "ERROR"}])
    observations = evaluation_inputs(bundle, "FROZEN_HOLDOUT")["observations"]
    observations[0]["receipt"][field] = "a" * 64
    seal_receipt(observations[0]["receipt"])
    with pytest.raises(evaluation.RerankerEvaluationError, match="OBSERVATION_SOURCE_BINDING"):
        evaluate(bundle, observations=observations)


def test_unavailable_missing_fingerprints_remain_limits_and_in_full_denominator():
    bundle = dataset([{"status": "UNAVAILABLE_MODEL"}])
    observations = evaluation_inputs(bundle, "FROZEN_HOLDOUT")["observations"]
    receipt = observations[0]["receipt"]
    for field in ("model_sha256", "scorer_sha256", "feature_schema_sha256", "config_sha256", "query_sha256", "input_sha256"):
        receipt[field] = None
    receipt.update(backend=None, data_kind="UNAVAILABLE", actual_model_available=False)
    seal_receipt(receipt)
    report = evaluate(bundle, observations=observations)
    assert report["rows"][0]["action"] == "UNAVAILABLE" and len(report["rows"][0]["binding_limits"]) >= 6
    assert report["metrics"]["mrr_all_work_operational"]["denominator"] == 1
    assert report["metrics"]["gold_present_selection_accuracy"]["denominator"] == 1


@pytest.mark.parametrize("change", ["drop", "duplicate", "foreign", "order", "nonfinite", "role"])
def test_success_requires_full_frozen_ids_finite_scores_ties_and_original_role_observations(change):
    bundle = dataset()
    observations = evaluation_inputs(bundle, "FROZEN_HOLDOUT")["observations"]
    receipt = observations[0]["receipt"]
    if change == "drop":
        receipt["ranked_candidates"].pop()
    elif change == "duplicate":
        receipt["ranked_candidates"][1] = deepcopy(receipt["ranked_candidates"][0])
    elif change == "foreign":
        receipt["ranked_candidates"][0]["candidate_id"] = "foreign-id"
    elif change == "order":
        receipt["ranked_candidates"].reverse()
    elif change == "role":
        receipt["candidate_observations"][0]["role_observations"] = []
    else:
        receipt["ranked_candidates"][0]["score"] = float("nan")
    if change != "nonfinite":
        seal_receipt(receipt)
    with pytest.raises(evaluation.RerankerEvaluationError):
        evaluate(bundle, observations=observations)


def test_query_fragment_omission_is_rejected_even_with_an_internally_valid_empty_view():
    bundle = dataset([{"status": "EMPTY_QUERY"}])
    expected = evaluation_inputs(bundle, "FROZEN_HOLDOUT")["expected_rows"]
    view = expected[0]["frozen_view"]
    view["source_view"]["fragments"] = []
    for item in view["candidates"]:
        item["role_observations"] = []
    with pytest.raises(evaluation.RerankerEvaluationError, match="SOURCE_FRAGMENT_ORDER_OR_COVERAGE_MISMATCH"):
        evaluate(bundle, expected_rows=expected)


def test_capture_and_candidate_title_bytes_are_checked_independently_of_score_receipt():
    bundle = dataset()
    expected = evaluation_inputs(bundle, "FROZEN_HOLDOUT")["expected_rows"]
    expected[0]["capture_sha256"] = "a" * 64
    with pytest.raises(evaluation.RerankerEvaluationError, match="CAPTURE_BYTES"):
        evaluate(bundle, expected_rows=expected)
    expected = evaluation_inputs(bundle, "FROZEN_HOLDOUT")["expected_rows"]
    expected[0]["candidate_text_bindings"][0]["titles"][0]["utf8_byte_span_start"] += 1
    with pytest.raises(evaluation.RerankerEvaluationError, match="TEXT_"):
        evaluate(bundle, expected_rows=expected)


def test_explicit_bridge_is_required_and_titles_are_not_used_to_guess_gold_id():
    bundle = dataset()
    policy = fit(bundle)["policy"]
    row = bundle["manifest"]["rows"][-1]
    row["r2_id_bridges"][0].update(status="MISSING", candidate_ids=[])
    bundle["manifest"] = split.seal_manifest(bundle["manifest"])
    # 이 시험의 합성 model summary만 새 split에 맞춰 bridge 검사를 분리한다.
    bundle["model"]["training_split_manifest_sha256"] = bundle["manifest"]["manifest_sha256"]
    with pytest.raises(evaluation.RerankerEvaluationError, match="EXPLICIT_UNIQUE_ID_BRIDGE_REQUIRED"):
        evaluate(bundle, policy)


def test_calibration_uses_only_cal_rows_to_select_thresholds():
    bundle = dataset()
    first = fit(bundle, score_thresholds=[4, 2, 0], margin_thresholds=[3, 1, 0])
    bundle["specs"]["example-3"]["scores"] = [-100, 999, 0]
    second = fit(bundle, score_thresholds=[0, 4, 2], margin_thresholds=[0, 3, 1])
    assert first == second
    assert first["policy"]["score_threshold"] == 0 and first["policy"]["margin_threshold"] == 0
    frozen = evaluate(bundle, second["policy"])
    assert frozen["metrics"]["selective_risk"]["value"] == 1
    assert frozen["policy_sha256"] == second["policy"]["policy_sha256"]


def test_cal_without_covered_decisions_cannot_claim_zero_risk_or_issue_policy():
    result = fit(dataset(), score_thresholds=[999])
    assert result["status"] == "NO_FEASIBLE_POLICY" and result["policy"] is None and result["metrics"] is None


def test_unknown_labels_stay_not_ready_and_never_become_nil():
    bundle = dataset([{"truth": "UNJUDGED"}])
    report = fit(bundle)
    assert report["status"] == "NOT_ESTIMABLE_SPLIT_NOT_READY" and report["policy"] is None
    assert any(issue["code"] == "TRUTH_UNJUDGED" for issue in report["split_issues"])
    assert report["metrics"] is None


@pytest.mark.parametrize("kind", ["unsealed", "resealed", "new_model", "new_split"])
def test_frozen_policy_requires_external_pin_and_exact_model_and_split(kind):
    bundle = dataset()
    policy = fit(bundle)["policy"]
    expected = policy["policy_sha256"]
    if kind in {"unsealed", "resealed"}:
        policy["score_threshold"] = 999
        if kind == "resealed":
            policy["policy_sha256"] = evaluation.canonical_sha256({key: value for key, value in policy.items() if key != "policy_sha256"})
    else:
        policy["model_binding_sha256" if kind == "new_model" else "split_manifest_sha256"] = "a" * 64
        policy["policy_sha256"] = evaluation.canonical_sha256({key: value for key, value in policy.items() if key != "policy_sha256"})
        expected = policy["policy_sha256"]
    with pytest.raises(evaluation.RerankerEvaluationError, match="POLICY_"):
        evaluate(bundle, policy, expected_policy_sha256=expected)


def actual_scorer(bundle, tmp_path):
    from src.llm_batch.grounding import candidate_reranker_learned as learned
    train_expected = evaluation_inputs(bundle, "TRAIN")["expected_rows"]
    examples = [{key: value for key, value in row.items() if key != "publication_scope_id"} for row in train_expected]
    trained = learned.train_model(bundle["manifest"], source_payloads=bundle["source"],
        evidence_payloads=bundle["evidence"], examples=examples, config={"epochs": 2})
    envelope = {"schema_version": "candidate_reranker_manifest_v2", "scorer_id": "synthetic-test-learned",
        "backend": learned.BACKEND, "data_kind": "SYNTHETIC_FIXTURE", "feature_schema": learned.FEATURE_SCHEMA,
        "model": trained["model"]}
    path = tmp_path / "learned_manifest.json"
    encoded = raw(envelope)
    path.write_bytes(encoded)
    scorer = adapter.load_scorer(path, expected_sha256=sha(encoded))
    bundle["model"] = scorer.summary()
    assert bundle["model"]["training_split_manifest_sha256"] == trained["model"]["training_binding"]["split_manifest_sha256"]
    return scorer


def actual_inputs(bundle, scorer, partition):
    args = evaluation_inputs(bundle, partition)
    for expected, observation in zip(args["expected_rows"], args["observations"]):
        receipt = scorer.score(expected["frozen_view"])
        assert receipt["status"] == "SCORED_LEARNED"
        binding = observation["receipt"]["binding"]
        emitted = export_candidate_reranker_fields(SimpleNamespace(_candidate_reranker_shadow=receipt),
            scorer, binding=binding)["candidate_reranker_shadow"]
        assert emitted["status"] == "SCORED_LEARNED"
        assert emitted["candidate_set_fingerprint"] is None
        assert emitted["binding"]["scope"] == "ATTEMPT_LOCAL_OBSERVATION"
        assert emitted["training_split_manifest_sha256"] == bundle["model"]["training_split_manifest_sha256"]
        observation["receipt"] = emitted
    return args


def test_real_learned_model_adapter_and_runtime_export_receipts_feed_cal_and_frozen(tmp_path):
    """실제 작은 optimizer·저장/로드·producer/export를 연결하되 자료는 합성이다."""
    bundle = dataset()
    scorer = actual_scorer(bundle, tmp_path)
    cal = evaluation.fit_calibration_thresholds(**actual_inputs(bundle, scorer, "CALIBRATION"),
        score_thresholds=[-1000], margin_thresholds=[0], max_empirical_risk=1)
    assert cal["status"] == "CAL_POLICY_FROZEN"
    report = evaluation.evaluate_frozen_scores(**actual_inputs(bundle, scorer, "FROZEN_HOLDOUT"),
        threshold_policy=cal["policy"], expected_policy_sha256=cal["policy"]["policy_sha256"])
    assert report["status"] == "FROZEN_SCORE_EVALUATED" and report["evidence_scope"] == "SYNTHETIC_ONLY"
    assert report["counts"]["source_terminals"]["SCORED_LEARNED"] == 1


def test_actual_trained_model_cannot_reclassify_its_train_rows_as_frozen(tmp_path):
    bundle = dataset()
    scorer = actual_scorer(bundle, tmp_path)
    old_split_sha = bundle["model"]["training_split_manifest_sha256"]
    bundle["manifest"]["rows"][0]["assignment"]["split"] = "FROZEN_HOLDOUT"
    bundle["manifest"]["rows"][3]["assignment"]["split"] = "TRAIN"
    bundle["manifest"] = split.seal_manifest(bundle["manifest"])
    validation = split.validate_training_split(bundle["manifest"], source_payloads=bundle["source"],
                                              evidence_payloads=bundle["evidence"])
    assert validation["status"] == "VALID" and bundle["manifest"]["manifest_sha256"] != old_split_sha
    # CAL 원문과 실제 score receipt는 그대로여도 새 CAL 정책 발급부터 거절한다.
    with pytest.raises(evaluation.RerankerEvaluationError, match="MODEL_TRAINING_SPLIT_MISMATCH"):
        evaluation.fit_calibration_thresholds(**actual_inputs(bundle, scorer, "CALIBRATION"),
            score_thresholds=[-1000], margin_thresholds=[0], max_empirical_risk=1)


@pytest.mark.parametrize("fault", ["missing", "invalid", "different"])
def test_model_training_split_binding_is_required_before_calibration(fault):
    bundle = dataset()
    if fault == "missing":
        del bundle["model"]["training_split_manifest_sha256"]
        code = "MODEL_BINDING_MISSING"
    elif fault == "invalid":
        bundle["model"]["training_split_manifest_sha256"] = None
        code = "MODEL_SHA_INVALID"
    else:
        bundle["model"]["training_split_manifest_sha256"] = "a" * 64
        code = "MODEL_TRAINING_SPLIT_MISMATCH"
    with pytest.raises(evaluation.RerankerEvaluationError, match=code):
        fit(bundle)
