"""실제 semantic producer의 합성 TRAIN/NIL/CAL 산출물과 저장 readback 연결 시험."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from src.llm_batch.measurement import candidate_reranker_actual_bridge as pair
from src.llm_batch.grounding import candidate_reranker_calibration as temperature
from src.llm_batch.grounding import candidate_reranker_shadow as scorer_api
from src.llm_batch.grounding import candidate_set_calibration_shadow as legacy
from src.llm_batch.grounding import calibration_actual_readback as readback
from tests.candidate_reranker_semantic_calibration_fixtures import build_semantic_calibration_fixture


def train_examples_from_saved_semantics(fixture):
    """기존 합성 TRAIN 원문·role span으로 원래 capture의 exact 입력을 복원한다."""
    examples = []
    captures = {}
    for digest, content in fixture["evidence_payloads"].items():
        try:
            value = json.loads(content)
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict) and value.get("schema_version") == "reranker_preselection_capture_v2":
            captures[value["example_id"]] = (digest, value)
    for row in fixture["training_manifest"]["rows"]:
        if row["assignment"]["split"] != "TRAIN":
            continue
        eid = row["assignment"]["example_id"]
        capture_sha, capture = captures[eid]
        view = deepcopy(fixture["semantic_inputs"][eid]["enriched_view"])
        by_corpus = {e["corpus_candidate_id"]: e["candidate_id"] for e in row["exposures"]}
        by_candidate = {m["candidate_id"]: m["source_span"] for m in row["role_mentions"]}
        bindings = [{"candidate_id": c["candidate_id"], "titles": [deepcopy(by_candidate[by_corpus[c["candidate_id"]]])],
            "aliases": []} for c in view["candidates"]]
        assert pair.event.canonical_sha256(view) == capture["frozen_view_sha256"]
        assert pair.event.canonical_sha256(bindings) == capture["candidate_text_bindings_sha256"]
        examples.append({"example_id": eid, "frozen_view": view,
            "candidate_text_bindings": bindings, "capture_sha256": capture_sha})
    return examples


def independently_train_baseline(fixture, target):
    """같은 사건 공간에서 두 번째 optimizer 실행·CAL fit을 별도로 수행한다."""
    from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
    from tests.candidate_reranker_semantic_calibration_fixtures import _bind_semantic_graph
    target.mkdir()
    evidence = dict(fixture["evidence_payloads"])
    trained = nil.train_model(fixture["training_manifest"], source_payloads=fixture["source_payloads"],
        evidence_payloads=evidence, examples=train_examples_from_saved_semantics(fixture),
        config={"base": {"epochs": 5, "learning_rate": 0.05}, "nil_head": {"epochs": 7, "learning_rate": 0.7}},
        feature_schema=nil.FEATURE_SCHEMA_V2)
    envelope = {"schema_version": scorer_api.NIL_MANIFEST_SCHEMA, "scorer_id": "independently-trained-baseline",
        "backend": nil.BACKEND, "data_kind": "SYNTHETIC_FIXTURE", "feature_schema": nil.FEATURE_SCHEMA_V2,
        "model": trained["model"]}
    model_raw = pair._raw(envelope)
    path = target / "baseline_model.json"
    with path.open("xb") as stream: stream.write(model_raw)
    scorer = scorer_api.load_scorer(path, expected_sha256=pair._sha(model_raw))
    summary = scorer.summary()
    common = {**fixture["common_kwargs"], "scorer_summary": summary,
        "expected_scorer_summary_sha256": pair.event.canonical_sha256(summary), "evidence_payloads": evidence}
    cal_rows, frozen_args = [], []
    for original, destination in [(r, cal_rows) for r in fixture["cal_rows"]] + [(r, frozen_args) for r in fixture["frozen_args"]]:
        item = {k: original[k] for k in pair.nil_eval.GRAPH_KEYS if k != "source_binding_sha256"}
        item["example"] = deepcopy(item["example"])
        eid = item["example"]["example_id"]
        item["raw_receipt"] = scorer.score(item["example"]["frozen_view"],
            semantic_input=fixture["semantic_inputs"][eid], evidence_payloads=evidence)
        args = {**common, **item}
        _bind_semantic_graph(args)
        item["source_binding_sha256"] = args["source_binding_sha256"]
        destination.append({**common, **item} if destination is frozen_args else item)
    events = pair.event.build_calibration_fit_events(**common, rows=cal_rows,
        expected_example_ids=fixture["expected_calibration_example_ids"])
    result = {**fixture, "scorer": scorer, "scorer_summary": summary, "model": trained["model"],
        "model_manifest": envelope, "model_manifest_path": path, "model_manifest_sha256": pair._sha(model_raw),
        "evidence_payloads": evidence, "common_kwargs": common, "cal_rows": cal_rows,
        "calibration_events": events, "frozen_args": frozen_args,
        "frozen_vectors": {r["example"]["example_id"]: pair.event.build_frozen_event_score(**r) for r in frozen_args}}
    artifact = temperature.fit_temperature(events, split_manifest=fixture["calibration_manifest"],
        policy=fixture["policy"])["artifact"]
    return result, artifact


@pytest.fixture(scope="module")
def semantic_bundle(tmp_path_factory):
    fixture = build_semantic_calibration_fixture(tmp_path_factory.mktemp("actual-bridge-semantic"), with_alias=True)
    artifact = temperature.fit_temperature(fixture["calibration_events"], split_manifest=fixture["calibration_manifest"],
        policy=fixture["policy"])["artifact"]
    return fixture, artifact


@pytest.fixture(scope="module")
def paired_semantic_bundle(semantic_bundle, tmp_path_factory):
    after, after_artifact = semantic_bundle
    baseline, baseline_artifact = independently_train_baseline(after,
        tmp_path_factory.mktemp("independent-actual-baseline") / "model")
    assert after["model"] != baseline["model"]
    assert after["scorer_summary"]["model_sha256"] != baseline["scorer_summary"]["model_sha256"]
    assert after_artifact.artifact_sha256 != baseline_artifact.artifact_sha256
    assert any(a["raw_receipt"]["event_logits"] != b["raw_receipt"]["event_logits"]
        for a, b in zip(after["frozen_args"], baseline["frozen_args"]))
    return after, after_artifact, baseline, baseline_artifact


def arm_for(fixture, artifact):
    expected, observed, graphs = [], [], []
    by_id = {r["assignment"]["example_id"]: r for r in fixture["training_manifest"]["rows"]}
    for args in fixture["frozen_args"]:
        example = deepcopy(args["example"])
        receipt = deepcopy(args["raw_receipt"])
        row = by_id[example["example_id"]]
        receipt["binding"] = {**row["binding"], "post_id": row["assignment"]["post_id"],
            "publication_scope_id": args["publication_scope_id"], "scope": "ATTEMPT_LOCAL_OBSERVATION"}
        expected.append({**example, "publication_scope_id": args["publication_scope_id"]})
        observed.append({"example_id": example["example_id"], "receipt": receipt})
        graphs.append({k: deepcopy(args[k]) if k in ("example", "raw_receipt") else args[k]
            for k in pair.nil_eval.GRAPH_KEYS})
    return pair.FrozenArmInput(**fixture["common_kwargs"], policy=fixture["policy"], calibration_artifact=artifact,
        expected_rows=expected, observations=observed, frozen_rows=graphs)


def source_inputs(arm):
    """새 wrapper만 생성하며 원문 bytes·span·행 ID는 기존 fixture에서 그대로 가져온다."""
    expected = [a.to_dict() for a in arm.calibration_manifest.assignments if a.split == "FROZEN_HOLDOUT"]
    records, payloads = [], {}
    for row in pair._rows(arm):
        a = row["assignment"]
        refs = [{"source_id": sid, "payload_sha256": pair._sha(arm.source_payloads[sid]),
            "bytes": len(arm.source_payloads[sid])} for sid in sorted(row["source_ids"])]
        value = {"schema_version": pair.PAYLOAD_SCHEMA, "source_run_id": "synthetic-structural-only",
            "example_id": a["example_id"], "post_id": a["post_id"],
            "payload": {"schema_version": pair.ALIGNMENT_SCHEMA, "source_spans": deepcopy(row["source_spans"]), "source_refs": refs}}
        raw = pair._raw(value)
        payloads[pair._sha(raw)] = raw
        records.append({"example_id": a["example_id"], "post_id": a["post_id"], "source_artifact": {
            "logical_name": "source_payload::" + a["example_id"], "relative_path": "source/" + a["example_id"] + ".json",
            "bytes": len(raw), "sha256": pair._sha(raw), "canonical_payload_sha256": pair.event.canonical_sha256(value),
            "row_count": None}})
    manifest = {"schema_version": pair.SOURCE_SCHEMA, "source_run_id": "synthetic-structural-only", "rows": records}
    manifest["manifest_sha256"] = pair.event.canonical_sha256(manifest)
    raw = pair._raw(manifest); payloads[pair._sha(raw)] = raw
    return dict(expected_universe=expected, source_manifest=manifest, source_manifest_raw_sha256=pair._sha(raw),
                actual_source_payloads=payloads)


def prepare(fixture, artifact, **options):
    a, b = arm_for(fixture, artifact), arm_for(fixture, artifact)
    return pair.prepare_actual_pair(after=a, baseline=b, **source_inputs(a), **options)


def test_semantic_alias_train_cal_frozen_pair_keeps_all_pins_without_model_or_fit(semantic_bundle, monkeypatch):
    fixture, artifact = semantic_bundle
    a, b = arm_for(fixture, artifact), arm_for(fixture, artifact)
    sources = source_inputs(a)
    before = pair._raw({"source": sources["source_manifest"], "expected": a.expected_rows, "observed": a.observations})
    monkeypatch.setattr(scorer_api.FrozenCandidateRerankerShadow, "score", lambda *a, **k: pytest.fail("순수 bridge의 score 금지"))
    monkeypatch.setattr(temperature, "fit_temperature", lambda *a, **k: pytest.fail("새 fit 금지"))
    report = pair.prepare_actual_pair(after=a, baseline=b, **sources)
    assert report["status"] == "READY_FOR_BOUND_READBACK"
    assert report["expected_count"] == len(report["per_row"]) == 2
    assert "AFTER_SYNTHETIC_NOT_ACTUAL" in report["actual_admission_reasons"]
    assert "ACTUAL_POLICY_V4_NOT_PREREGISTERED" in report["actual_admission_reasons"]
    assert report["quality_acceptance_claimed"] is report["publication_authority"] is False
    assert report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert report["pair_sha256"] == pair.event.canonical_sha256({k: v for k, v in report.items() if k != "pair_sha256"})
    assert before == pair._raw({"source": sources["source_manifest"], "expected": a.expected_rows, "observed": a.observations})
    report["artifact_payloads"]["prediction"][0]["post_id"] = "changed-output"
    assert a.expected_rows == b.expected_rows
    assert prepare(fixture, artifact)["artifact_payloads"]["prediction"][0]["post_id"] != "changed-output"


def test_pair_files_roundtrip_through_existing_actual_parsers_and_independent_readback(paired_semantic_bundle, tmp_path):
    from tools import run_candidate_set_calibration_shadow_harness as runner
    fixture, artifact, baseline_fixture, baseline_artifact = paired_semantic_bundle
    arm = arm_for(fixture, artifact); source = source_inputs(arm)
    report = pair.prepare_actual_pair(after=arm, baseline=arm_for(baseline_fixture, baseline_artifact), **source)
    payloads = {"expected_universe": source["expected_universe"], **report["artifact_payloads"]}
    refs = {}
    for name, value in payloads.items():
        is_rows = type(value) is list
        path = tmp_path / (name + (".jsonl" if is_rows else ".json"))
        path.write_bytes(b"".join(pair._raw(r) + b"\n" for r in value) if is_rows else pair._raw(value))
        refs[name] = readback.snapshot_artifact(tmp_path, name, path.name, jsonl=is_rows)
    frozen = [a for a in arm.calibration_manifest.assignments if a.split == "FROZEN_HOLDOUT"]
    runner._validate_actual_replay_bundle(root=tmp_path, refs=refs, frozen=frozen,
        split_manifest=arm.calibration_manifest, policy=arm.policy, prediction_rows=payloads["prediction"],
        baseline_rows=payloads["baseline_prediction"])
    manifest = readback.build_readback_manifest(run_spec_sha256="1" * 64, artifacts=refs,
        expected_universe=readback.expected_universe_readback(payloads["expected_universe"]),
        producer_coverage=readback.producer_coverage_receipt(payloads["expected_universe"], payloads["producer"]),
        prediction=readback.prediction_payload_readback(payloads["expected_universe"], payloads["prediction"]),
        baseline_prediction=readback.prediction_payload_readback(payloads["expected_universe"], payloads["baseline_prediction"]),
        source_digest_sha256=source["source_manifest_raw_sha256"], metric_protocol_sha256=arm.policy.policy_sha256,
        bootstrap_seed=7, bootstrap_replicates=2000)
    recovered = readback.validate_actual_readback_artifacts(tmp_path, manifest)
    assert recovered["prediction"] == payloads["prediction"]
    assert recovered["baseline_prediction"] == payloads["baseline_prediction"]
    assert payloads["after_calibration_artifact"] == artifact.to_dict()
    assert payloads["baseline_calibration_artifact"] == baseline_artifact.to_dict()
    assert payloads["after_score_vectors"] == [s.to_dict() for s in fixture["frozen_vectors"].values()]
    assert payloads["baseline_score_vectors"] == [s.to_dict() for s in baseline_fixture["frozen_vectors"].values()]
    for name, data, fitted in (("prediction", fixture, artifact), ("baseline_prediction", baseline_fixture, baseline_artifact)):
        for row in payloads[name]:
            eid = row["example_id"]
            expected_shadow = legacy.build_calibration_shadow(data["frozen_base_shadows"][eid],
                data["frozen_vectors"][eid], fitted, data["policy"], split_manifest=data["calibration_manifest"],
                assignment=data["frozen_assignments"][eid])
            assert row["calibration_shadow"] == expected_shadow.to_dict()
    # 같은 bytes를 읽었다는 구조 검증이다. 합성 policy를 actual로 바꾸지 않는다.
    result = legacy.evaluate_frozen_holdout(split_manifest=arm.calibration_manifest, shadows={}, policy=arm.policy,
        evidence_mode="FROZEN_ACTUAL")
    assert result["status"] == "NO_GO_POLICY_SCOPE_MISMATCH"
    target = tmp_path / "prediction.jsonl"
    changed = deepcopy(payloads["prediction"]); changed[0]["probabilities"]["__NIL__"] += 1
    target.write_bytes(b"".join(pair._raw(r) + b"\n" for r in changed))
    with pytest.raises(ValueError):
        readback.validate_actual_readback_artifacts(tmp_path, manifest)


@pytest.mark.parametrize("copy_after", ["observations", "artifact"])
def test_distinct_baseline_cannot_be_replaced_with_after_arm(paired_semantic_bundle, copy_after):
    af, aa, bf, ba = paired_semantic_bundle
    a, b = arm_for(af, aa), arm_for(bf, ba)
    if copy_after == "observations":
        b = replace(b, observations=deepcopy(a.observations), frozen_rows=[])
    else:
        b = replace(b, calibration_artifact=aa)
    with pytest.raises(ValueError):
        pair.prepare_actual_pair(after=a, baseline=b, **source_inputs(a))


@pytest.fixture(scope="module")
def plain_bundle(tmp_path_factory):
    from tests.candidate_reranker_calibration_fixtures import build_calibration_fixture
    fixture = build_calibration_fixture(tmp_path_factory.mktemp("actual-bridge-v1-terminals"))
    artifact = temperature.fit_temperature(fixture["calibration_events"], split_manifest=fixture["calibration_manifest"],
        policy=fixture["policy"])["artifact"]
    return fixture, artifact


def terminal_pair(plain_bundle, terminal, affected_arm):
    """v1 NIL 실제 scorer terminal과 기존 raw capture helper를 사용한다."""
    from tests.test_candidate_reranker_nil_evaluation import inputs, rescore, rebind_graph
    fixture, artifact = plain_bundle
    arms = {name: inputs(fixture, artifact) for name in ("after", "baseline")}
    args = arms[affected_arm]
    exp = args["expected_rows"][0]
    if terminal == "TRUNCATED":
        exp["frozen_view"]["generation_status"] = "TRUNCATED"
    elif terminal == "EMPTY":
        exp["frozen_view"]["candidates"] = []
        exp["candidate_text_bindings"] = []
    else:
        row = next(r for r in args["training_manifest"]["rows"] if r["assignment"]["example_id"] == exp["example_id"])
        gold = row["assignment"]["truth_label"]
        cid = next(b["corpus_candidate_id"] for b in row["r2_id_bridges"] if b["candidate_ids"] == [gold])
        exp["frozen_view"]["candidates"] = [c for c in exp["frozen_view"]["candidates"] if c["candidate_id"] != cid]
        exp["candidate_text_bindings"] = [c for c in exp["candidate_text_bindings"] if c["candidate_id"] != cid]
    rescore(args, fixture, 0)
    if terminal == "GOLD_MISS":
        rebind_graph(args, 0)
    else:
        args["frozen_rows"] = args["frozen_rows"][1:]
    return {name: pair.FrozenArmInput(**value) for name, value in arms.items()}


@pytest.mark.parametrize("terminal", ["EMPTY", "TRUNCATED", "GOLD_MISS"])
@pytest.mark.parametrize("affected_arm", ["after", "baseline"])
def test_paired_semantic_ineligible_rows_keep_full_denominator(plain_bundle, terminal, affected_arm):
    arms = terminal_pair(plain_bundle, terminal, affected_arm)
    report = pair.prepare_actual_pair(**arms, **source_inputs(arms["after"]))
    assert report["expected_count"] == len(report["per_row"]) == 2
    assert report["after_report"]["counts"]["expected_rows"] == report["baseline_report"]["counts"]["expected_rows"] == 2
    assert report["status"] == "NOT_EVALUABLE" and report["artifact_payloads"] is None
    row = report[affected_arm + "_report"]["rows"][0]
    assert row["calibration_shadow"] is None and row["truth_kind"] == "CANDIDATE"
    raw_receipt = arms[affected_arm].observations[0]["receipt"]
    if terminal == "GOLD_MISS":
        assert row["source_terminal"] == "SCORED_LEARNED" and row["gold_present"] is False
        assert "GOLD_CANDIDATE_NOT_RETRIEVED" in row["calibration_reason_codes"]
        assert report[affected_arm + "_report"]["rank_metrics"]["gold_present_top1_accuracy"]["denominator"] == 0
    else:
        assert row["source_terminal"] == ("EMPTY_CANDIDATE_SET" if terminal == "EMPTY" else "NOT_SCORED_GENERATION_TRUNCATED")
        assert raw_receipt["nil_score"] is None and raw_receipt["event_logits"] == []
        assert row["action"] == ("ABSTAIN" if terminal == "EMPTY" else "UNAVAILABLE")


def test_valid_abstain_preserves_probabilities_and_each_fixed_fit(paired_semantic_bundle):
    af, aa, bf, ba = paired_semantic_bundle
    value = af["policy"].to_dict(); value.pop("policy_sha256")
    value.update(selector_max_error_probability=0.0, nil_min_probability=1.0)
    policy = legacy.CalibrationEvaluationPolicy.create(**value)
    arms = []
    for fixture in (af, bf):
        artifact = temperature.fit_temperature(fixture["calibration_events"],
            split_manifest=fixture["calibration_manifest"], policy=policy)["artifact"]
        arms.append(replace(arm_for(fixture, artifact), policy=policy))
    report = pair.prepare_actual_pair(after=arms[0], baseline=arms[1], **source_inputs(arms[0]))
    assert report["status"] == "READY_FOR_BOUND_READBACK"
    for key in ("prediction", "baseline_prediction"):
        for row in report["artifact_payloads"][key]:
            assert row["calibration_shadow"]["action"] == "ABSTAIN"
            assert sum(row["probabilities"].values()) == 1000000
            assert len(row["probabilities"]) > 1 and all(v > 0 for v in row["probabilities"].values())
    assert report["actual_admission_reasons"]  # ABSTAIN 확률 보존은 actual 적격성 승격이 아니다.


def test_unjudged_requires_new_valid_training_contract_and_never_relabels_old_fit(paired_semantic_bundle):
    from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
    from src.llm_batch.grounding import reranker_training_split as split
    fixture, artifact, _, _ = paired_semantic_bundle
    manifest = deepcopy(fixture["training_manifest"])
    row = next(r for r in manifest["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT")
    row["assignment"].update(truth_kind="UNJUDGED", truth_label=None, matched_candidate_ids=[],
        binding_status="NOT_APPLICABLE", gold_work_fingerprint=None)
    row["label_provenance"]["grade"] = "UNJUDGED"
    manifest = split.seal_manifest(manifest)
    with pytest.raises(ValueError, match="FULL_SPLIT_NOT_VALID"):
        nil.train_model(manifest, source_payloads=fixture["source_payloads"], evidence_payloads=fixture["evidence_payloads"],
            examples=train_examples_from_saved_semantics(fixture), config={"base": {"epochs": 1}, "nil_head": {"epochs": 1}},
            feature_schema=nil.FEATURE_SCHEMA_V2)
    calibration = legacy.CalibrationSplitManifest.create(assignments=[legacy.CalibrationSplitAssignment(**a)
        for a in split.calibration_assignments(manifest)],
        source_label_ledger_sha256=fixture["calibration_manifest"].source_label_ledger_sha256,
        assignment_seed_sha256=fixture["calibration_manifest"].assignment_seed_sha256)
    a = replace(arm_for(fixture, artifact), training_manifest=manifest,
        expected_training_manifest_sha256=manifest["manifest_sha256"], calibration_manifest=calibration,
        expected_calibration_manifest_sha256=calibration.manifest_sha256)
    before = pair._raw(a.expected_rows)
    with pytest.raises(ValueError):
        pair.prepare_actual_pair(after=a, baseline=a, **source_inputs(a))
    assert len(a.expected_rows) == len(a.observations) == 2 and pair._raw(a.expected_rows) == before
    assert a.scorer_summary["training_split_manifest_sha256"] != manifest["manifest_sha256"]
    assert artifact.split_manifest_sha256 != calibration.manifest_sha256


@pytest.mark.parametrize("terminal", ["NOT_EXECUTED", "UNAVAILABLE_MODEL", "INVALID_INPUT"])
def test_real_terminals_preserve_both_full_denominators(semantic_bundle, terminal):
    from src.llm_batch.runtime.candidate_reranker import export_candidate_reranker_fields
    fixture, artifact = semantic_bundle
    a, b = arm_for(fixture, artifact), arm_for(fixture, artifact)
    binding = b.observations[0]["receipt"]["binding"]
    if terminal == "NOT_EXECUTED":
        receipt = export_candidate_reranker_fields(None, fixture["scorer"], binding=binding)["candidate_reranker_shadow"]
    elif terminal == "UNAVAILABLE_MODEL":
        unavailable = scorer_api.unavailable_scorer("MODEL_UNAVAILABLE", expected_sha256=fixture["scorer_summary"]["model_manifest_sha256"])
        receipt = unavailable.score(b.expected_rows[0]["frozen_view"])
    else:
        receipt = fixture["scorer"].score(b.expected_rows[0]["frozen_view"])
    receipt["binding"] = binding
    b.observations[0]["receipt"] = receipt
    b = replace(b, frozen_rows=b.frozen_rows[1:])
    result = pair.prepare_actual_pair(after=a, baseline=b, **source_inputs(a))
    assert result["status"] == "NOT_EVALUABLE" and result["artifact_payloads"] is None
    assert result["after_report"]["counts"]["expected_rows"] == result["baseline_report"]["counts"]["expected_rows"] == 2
    assert result["per_row"][0]["baseline_terminal"] == receipt["status"]


@pytest.mark.parametrize("fault", ["drop", "reorder", "typed_post", "source_bytes", "model_pin", "policy"])
def test_pair_never_normalizes_or_omits_mismatched_evidence(semantic_bundle, fault):
    fixture, artifact = semantic_bundle
    a, b = arm_for(fixture, artifact), arm_for(fixture, artifact); source = source_inputs(a)
    if fault == "drop": b = replace(b, observations=b.observations[1:])
    elif fault == "reorder": source["expected_universe"].reverse()
    elif fault == "typed_post": source["expected_universe"][0]["post_id"] = 9006
    elif fault == "source_bytes":
        values = dict(b.source_payloads); key = next(iter(values)); values[key] += b"changed"; b = replace(b, source_payloads=values)
    elif fault == "model_pin": b = replace(b, expected_scorer_summary_sha256="0" * 64)
    else:
        values = b.policy.to_dict(); values.pop("policy_sha256")
        values["selector_max_error_probability"] = 0.2 if b.policy.selector_max_error_probability != 0.2 else 0.3
        policy = legacy.CalibrationEvaluationPolicy.create(**values)
        assert policy.policy_sha256 != b.policy.policy_sha256
        with pytest.raises(ValueError, match="PAIR_SPLIT_POLICY_MISMATCH"):
            pair.prepare_actual_pair(after=a, baseline=replace(b, policy=policy), **source)
        return
    with pytest.raises((ValueError, KeyError)):
        pair.prepare_actual_pair(after=a, baseline=b, **source)


@pytest.mark.parametrize("field", ["source_spans", "source_refs", "post_id"])
def test_resealed_actual_source_cannot_hide_different_original(semantic_bundle, field):
    fixture, artifact = semantic_bundle
    a = arm_for(fixture, artifact); source = source_inputs(a)
    old_manifest = source["source_manifest_raw_sha256"]
    ref = source["source_manifest"]["rows"][0]["source_artifact"]
    original = source["actual_source_payloads"].pop(ref["sha256"])
    value = json.loads(original)
    if field == "source_spans": value["payload"][field][0]["text"] += "바뀐 원문"
    elif field == "source_refs": value["payload"][field][0]["payload_sha256"] = "b" * 64
    else: value[field] = "foreign-post"
    raw = pair._raw(value)
    ref.update(bytes=len(raw), sha256=pair._sha(raw), canonical_payload_sha256=pair.event.canonical_sha256(value))
    source["actual_source_payloads"][ref["sha256"]] = raw
    source["actual_source_payloads"].pop(old_manifest)
    manifest = source["source_manifest"]
    manifest["manifest_sha256"] = pair.event.canonical_sha256({k: v for k, v in manifest.items() if k != "manifest_sha256"})
    raw = pair._raw(manifest); source["source_manifest_raw_sha256"] = pair._sha(raw)
    source["actual_source_payloads"][pair._sha(raw)] = raw
    with pytest.raises(ValueError, match="ACTUAL_SOURCE"):
        pair.prepare_actual_pair(after=a, baseline=arm_for(fixture, artifact), **source)
