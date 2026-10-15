"""합성 TRAIN 모델과 실제 로컬 scorer를 잇는 순수 FROZEN bridge 계약 시험."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.llm_batch.grounding import candidate_reranker_event_bridge as bridge
from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
from src.llm_batch.grounding import candidate_reranker_shadow as adapter
from src.llm_batch.grounding import reranker_training_split as split
from src.llm_batch.grounding.candidate_generation import (
    build_candidate_generation_proof, build_candidate_producer_plan, build_candidate_producer_receipt,
)
from src.llm_batch.grounding.candidate_set_calibration_shadow import (
    CALIBRATION_SPLITS, CalibrationSplitAssignment, CalibrationSplitManifest, EventScoreVector,
)
from src.llm_batch.grounding.candidate_set_shadow import build_uncalibrated_selective_shadow
from src.llm_batch.promotion_gate import EvidenceRecord, GroundingState, RetrievalState, can_publish_title
from test_candidate_reranker_learned import training_fixture


def raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def seal_receipt(receipt):
    receipt["receipt_sha256"] = bridge.canonical_sha256({k: v for k, v in receipt.items()
        if k not in {"receipt_sha256", "latency_ms", "binding"}})


def complete_proof(titles):
    """합성 producer 입력/출력 선언만 구성한다. 검색·fetch는 실행하지 않는다."""
    plans, receipts = [], []
    for producer, key, value in (("search", "query", "synthetic query"),
                                  ("fetch", "url", "https://example.invalid/synthetic")):
        plan = build_candidate_producer_plan([{key: value, "purpose": "synthetic"}],
            producer=producer, enumeration_finished=True)
        receipts.append(build_candidate_producer_receipt(
            [{"title": title, "url": f"https://example.invalid/{i}"} for i, title in enumerate(titles)],
            {"attempted_count": 1, "raw_count": len(titles), "enumeration_finished": True},
            producer=producer, operation_input=value, purpose="synthetic", plan_fingerprint=plan.plan_fingerprint))
        plans.append(plan)
    proof = build_candidate_generation_proof(plans, receipts, local_snapshots=["UNKNOWN"])
    assert proof.status == "COMPLETE"
    return proof


def graph_record(args):
    """독립적으로 명시한 fixture schema. 제품의 projection 함수를 부르지 않는다."""
    row = next(r for r in args["training_manifest"]["rows"]
               if r["assignment"]["example_id"] == args["example"]["example_id"])
    ex, base = args["example"], args["base_shadow"]
    view, receipt = ex["frozen_view"], args["raw_receipt"]
    mapping = {r["corpus_candidate_id"]: r["candidate_ids"][0] for r in row["r2_id_bridges"]}
    return {"schema_version": "candidate_reranker_event_source_binding_v1", "stage": "PRE_SELECTION",
        "authority": "DECLARED_SOURCE_GRAPH_BINDING_NOT_INDEPENDENTLY_VERIFIED",
        "example_id": ex["example_id"], "post_id": row["assignment"]["post_id"],
        "binding": {**row["binding"], "publication_scope_id": args["publication_scope_id"]},
        "source_spans_sha256": bridge.canonical_sha256(row["source_spans"]),
        "capture_sha256": ex["capture_sha256"], "query_sha256": bridge.canonical_sha256(view["source_view"]),
        "frozen_view_sha256": bridge.canonical_sha256(view), "raw_receipt_sha256": receipt["receipt_sha256"],
        "scorer_summary_sha256": bridge.canonical_sha256(args["scorer_summary"]),
        "training_split_manifest_sha256": args["training_manifest"]["manifest_sha256"],
        "calibration_split_manifest_sha256": args["calibration_manifest"].manifest_sha256,
        "base_shadow_fingerprint": base.shadow_fingerprint,
        "publication_input_fingerprint": base.input_fingerprint,
        "candidate_set_fingerprint": base.candidate_set.candidate_set_fingerprint,
        "observation_fingerprint": base.candidate_set.observation_fingerprint,
        "raw_generation_sha256": view["generation_sha256"],
        "generation_proof_fingerprint": args["generation_proof"].metadata_fingerprint,
        "retrieval_state_fingerprint": bridge.canonical_sha256(args["retrieval_state"].to_dict()),
        "candidate_id_mapping": [{"raw_candidate_id": c["candidate_id"], "candidate_option_id":
            mapping[c["candidate_id"]] if view["candidate_namespace"] == "CORPUS_CANDIDATE" else c["candidate_id"]}
            for c in view["candidates"]],
        "r2_id_bridges_sha256": bridge.canonical_sha256(row["r2_id_bridges"])}


def bind_graph(args, record=None):
    encoded = raw(graph_record(args) if record is None else record)
    args["source_binding_sha256"] = sha(encoded)
    args["evidence_payloads"][sha(encoded)] = encoded


def capture(args):
    ex = args["example"]
    row = next(r for r in args["training_manifest"]["rows"] if r["assignment"]["example_id"] == ex["example_id"])
    payload = {"schema_version": "reranker_preselection_capture_v1", "stage": "PRE_SELECTION",
        "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD", "example_id": ex["example_id"],
        "post_id": row["assignment"]["post_id"], "binding": row["binding"],
        "source_spans_sha256": bridge.canonical_sha256(row["source_spans"]),
        "candidate_set_fingerprint": row["assignment"]["candidate_set_fingerprint"],
        "frozen_view_sha256": bridge.canonical_sha256(ex["frozen_view"]),
        "candidate_text_bindings_sha256": bridge.canonical_sha256(ex["candidate_text_bindings"])}
    encoded = raw(payload)
    ex["capture_sha256"] = sha(encoded)
    args["evidence_payloads"][sha(encoded)] = encoded


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    manifest, sources, evidence, train_examples = training_fixture(include_nil=True)
    row = next(r for r in manifest["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT")
    titles = [m["source_span"]["text"] for m in row["role_mentions"]]
    state = GroundingState(post_id=row["assignment"]["post_id"], candidate_title=titles[0])
    records = [EvidenceRecord(kind="candidate_preservation", candidate_title=t, supports_publish=True) for t in titles]
    base = build_uncalibrated_selective_shadow(state, records, can_publish_title(state, records), generation_status="COMPLETE")
    actual_ids = {c.titles[0]: c.candidate_id for c in base.candidate_set.candidates}
    renamed = {e["candidate_id"]: actual_ids[t] for e, t in zip(row["exposures"], titles)}
    for exposure, id_bridge, mention in zip(row["exposures"], row["r2_id_bridges"], row["role_mentions"]):
        exposure["candidate_id"] = renamed[exposure["candidate_id"]]
        id_bridge["candidate_ids"] = [renamed[id_bridge["candidate_ids"][0]]]
        mention["candidate_id"] = renamed[mention["candidate_id"]]
    assignment = row["assignment"]
    assignment.update(truth_label=renamed[assignment["truth_label"]],
        matched_candidate_ids=[renamed[assignment["truth_label"]]],
        candidate_set_fingerprint=base.candidate_set.candidate_set_fingerprint)
    manifest = split.seal_manifest(manifest)
    candidates, bindings = [], []
    text = row["source_spans"][0]["text"]
    for exposure, mention in zip(row["exposures"], row["role_mentions"]):
        span, cid = mention["source_span"], exposure["corpus_candidate_id"]
        start = text.index(span["text"])
        candidates.append({"candidate_id": cid, "titles": [span["text"]], "urls": [], "aliases": [],
            "option_kind": "WORK_CANDIDATE", "event_eligible": True, "identity_conflict": False, "negative_evidence": [],
            "role_observations": [{"role": mention["roles"][0], "raw_path": "/content", "start": start,
                "end": start + len(span["text"]), "text_sha256": span["span_sha256"]}]})
        bindings.append({"candidate_id": cid, "titles": [deepcopy(span)], "aliases": []})
    order = sorted(range(len(candidates)), key=lambda i: row["exposures"][i]["candidate_id"], reverse=True)
    view = {"schema_version": adapter.VIEW_SCHEMA, "stage": "PRE_SELECTION", "post_id": assignment["post_id"],
        "source_view": {"schema_version": adapter.SOURCE_SCHEMA, "post_id": assignment["post_id"],
            "fragments": [{"raw_path": "/content", "kind": "BODY", "text": text}]},
        "candidate_namespace": "CORPUS_CANDIDATE", "generation_sha256": sha(b"synthetic-r2-receipt"),
        "candidate_set_fingerprint": None, "generation_status": "COMPLETE", "candidates": [candidates[i] for i in order]}
    ex = {"example_id": assignment["example_id"], "frozen_view": view,
          "candidate_text_bindings": [bindings[i] for i in order], "capture_sha256": None}
    args = {"example": ex, "training_manifest": manifest, "source_payloads": sources, "evidence_payloads": evidence}
    capture(args)
    # 외부 모델 연결 없이 새 합성 TRAIN 2행에 로컬 stdlib optimizer만 적용한다.
    model = nil.train_model(manifest, source_payloads=sources, evidence_payloads=evidence, examples=train_examples,
        config={"base": {"epochs": 2}, "nil_head": {"epochs": 2}})["model"]
    envelope = {"schema_version": adapter.NIL_MANIFEST_SCHEMA, "scorer_id": "synthetic-nil-event-bridge",
        "backend": nil.BACKEND, "data_kind": "SYNTHETIC_FIXTURE", "feature_schema": nil.FEATURE_SCHEMA, "model": model}
    encoded = raw(envelope)
    path = tmp_path_factory.mktemp("synthetic_nil_bridge") / "manifest.json"
    with path.open("xb") as stream:
        stream.write(encoded)
    scorer = adapter.load_scorer(path, expected_sha256=sha(encoded))
    calibration = CalibrationSplitManifest.create(assignments=[CalibrationSplitAssignment(**a)
        for a in split.calibration_assignments(manifest)], source_label_ledger_sha256=sha(b"synthetic-label-ledger"),
        assignment_seed_sha256=sha(b"synthetic-assignment-seed"))
    args.update(raw_receipt=scorer.score(view), scorer_summary=scorer.summary(),
        expected_scorer_summary_sha256=bridge.canonical_sha256(scorer.summary()),
        expected_training_manifest_sha256=manifest["manifest_sha256"], calibration_manifest=calibration,
        expected_calibration_manifest_sha256=calibration.manifest_sha256, base_shadow=base,
        generation_proof=complete_proof(titles), retrieval_state=RetrievalState(), publication_scope_id="synthetic-scope")
    bind_graph(args)
    return args, scorer


def test_real_producer_bridge_reorders_ids_and_keeps_two_manifest_domains_and_public_input(bundle):
    args, _ = bundle
    before = deepcopy(args)
    with patch.object(Path, "open", side_effect=AssertionError("bridge must not open files")):
        vector = bridge.build_frozen_event_score(**args)
    assert isinstance(vector, EventScoreVector) and args == before
    assert vector.split == "FROZEN_HOLDOUT" and vector.labels[-1] == "__NIL__"
    assert vector.labels[:-1] == tuple(c.candidate_id for c in args["base_shadow"].candidate_set.candidates)
    mapping = {r["raw_candidate_id"]: r["candidate_option_id"] for r in graph_record(args)["candidate_id_mapping"]}
    assert [mapping[cid] for cid in args["raw_receipt"]["frozen_candidate_ids"]] == list(reversed(vector.labels[:-1]))
    scores = {mapping[r["candidate_id"]]: r["score"] for r in args["raw_receipt"]["ranked_candidates"]}
    assert vector.raw_scores == tuple(scores[cid] for cid in vector.labels[:-1]) + (args["raw_receipt"]["nil_score"],)
    assert vector.split_manifest_sha256 == args["calibration_manifest"].manifest_sha256 != args["training_manifest"]["manifest_sha256"]
    assert vector.publication_input_fingerprint == before["base_shadow"].input_fingerprint
    assert vector.scorer_fingerprint == args["scorer_summary"]["scorer_sha256"]
    assert CALIBRATION_SPLITS == ("DEV", "CALIBRATION", "FROZEN_HOLDOUT")
    assert args["raw_receipt"]["nil_probability"] is None
    vector.validate()
    assert bridge.build_frozen_event_score(**args).to_dict() == vector.to_dict()


def test_direct_candidate_option_namespace_and_runtime_storage_binding(bundle):
    original, scorer = bundle
    args = deepcopy(original)
    view = args["example"]["frozen_view"]
    mapping = {r["raw_candidate_id"]: r["candidate_option_id"] for r in graph_record(args)["candidate_id_mapping"]}
    view["candidate_namespace"] = "CANDIDATE_OPTION"
    view["candidate_set_fingerprint"] = args["base_shadow"].candidate_set.candidate_set_fingerprint
    for c, bound in zip(view["candidates"], args["example"]["candidate_text_bindings"]):
        c["candidate_id"] = bound["candidate_id"] = mapping[c["candidate_id"]]
    capture(args)
    args["raw_receipt"] = scorer.score(view)
    row = next(r for r in args["training_manifest"]["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT")
    args["raw_receipt"]["binding"] = {**row["binding"], "post_id": row["assignment"]["post_id"],
        "publication_scope_id": args["publication_scope_id"], "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    bind_graph(args)
    assert bridge.build_frozen_event_score(**args).labels[-1] == "__NIL__"
    args["raw_receipt"]["binding"]["attempt_id"] = "different-attempt"
    with pytest.raises(bridge.EventBridgeError, match="RECEIPT_STORAGE_BINDING_MISMATCH"):
        bridge.build_frozen_event_score(**args)


@pytest.mark.parametrize("field", ["expected_training_manifest_sha256", "expected_calibration_manifest_sha256", "expected_scorer_summary_sha256"])
def test_external_pins_are_required(bundle, field):
    args = deepcopy(bundle[0])
    args[field] = "0" * 64
    with pytest.raises(bridge.EventBridgeError):
        bridge.build_frozen_event_score(**args)


@pytest.mark.parametrize("field", ["publication_input_fingerprint", "generation_proof_fingerprint", "retrieval_state_fingerprint",
    "training_split_manifest_sha256", "calibration_split_manifest_sha256", "query_sha256", "raw_receipt_sha256"])
def test_resealed_foreign_graph_binding_is_rejected(bundle, field):
    args = deepcopy(bundle[0])
    record = graph_record(args)
    record[field] = "0" * 64
    bind_graph(args, record)
    with pytest.raises(bridge.EventBridgeError, match="SOURCE_GRAPH_BINDING_MISMATCH"):
        bridge.build_frozen_event_score(**args)


@pytest.mark.parametrize("mutation", ["missing", "raw_sha", "duplicate_json", "scope"])
def test_source_graph_missing_raw_hash_duplicate_key_and_scope_fail(bundle, mutation):
    args = deepcopy(bundle[0])
    digest = args["source_binding_sha256"]
    if mutation == "missing":
        del args["evidence_payloads"][digest]
    elif mutation == "raw_sha":
        args["evidence_payloads"][digest] += b" "
    elif mutation == "scope":
        args["publication_scope_id"] = "other-scope"
    else:
        value = args["evidence_payloads"][digest][:-1] + b',"schema_version":"duplicate"}'
        args["source_binding_sha256"] = sha(value)
        args["evidence_payloads"][sha(value)] = value
    with pytest.raises(bridge.EventBridgeError):
        bridge.build_frozen_event_score(**args)


@pytest.mark.parametrize("mutation", ["event_order", "missing_event", "nil_score", "bool_score", "score_mismatch", "duplicate_candidate", "nonfinite", "status", "authority", "model", "viewsha"])
def test_resealed_raw_receipt_cannot_change_event_semantics(bundle, mutation):
    args = deepcopy(bundle[0])
    r = args["raw_receipt"]
    if mutation == "event_order": r["event_logits"].reverse()
    elif mutation == "missing_event": r["event_logits"].pop()
    elif mutation == "nil_score": r["nil_score"] = None
    elif mutation == "bool_score": r["nil_score"] = r["event_logits"][-1]["score"] = False
    elif mutation == "score_mismatch": r["event_logits"][0]["score"] += 1
    elif mutation == "duplicate_candidate": r["ranked_candidates"][0]["candidate_id"] = r["ranked_candidates"][1]["candidate_id"]
    elif mutation == "nonfinite": r["nil_score"] = float("inf")
    elif mutation == "status": r["status"] = "LIMIT_EXCEEDED"
    elif mutation == "authority": r["public_apply"] = True
    elif mutation == "model": r["candidate_ranker_model_sha256"] = "0" * 64
    else: r["query_sha256"] = "0" * 64
    if mutation != "nonfinite":
        seal_receipt(r)
        bind_graph(args)
    with pytest.raises(bridge.EventBridgeError):
        bridge.build_frozen_event_score(**args)


@pytest.mark.parametrize("mutation", ["source_bytes", "source_projection", "title_span", "missing_bridge", "wrong_bridge", "unjudged", "wrong_split"])
def test_source_exposure_and_split_changes_do_not_fabricate_an_event(bundle, mutation):
    args = deepcopy(bundle[0])
    row = next(r for r in args["training_manifest"]["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT")
    if mutation == "source_bytes": args["source_payloads"][row["source_ids"][0]] += b"changed"
    elif mutation == "source_projection": args["example"]["frozen_view"]["source_view"]["fragments"][0]["text"] += " 누락된 원문"
    elif mutation == "title_span": args["example"]["candidate_text_bindings"][0]["titles"][0]["utf8_byte_span_start"] += 1
    elif mutation == "missing_bridge": row["r2_id_bridges"].clear()
    elif mutation == "wrong_bridge": row["r2_id_bridges"][0]["candidate_ids"] = row["r2_id_bridges"][1]["candidate_ids"][:]
    elif mutation == "wrong_split": args["example"]["example_id"] = args["training_manifest"]["rows"][0]["assignment"]["example_id"]
    else: row["assignment"].update(truth_kind="UNJUDGED", truth_label=None, gold_work_fingerprint=None, binding_status="NOT_APPLICABLE", matched_candidate_ids=[])
    with pytest.raises(bridge.EventBridgeError):
        bridge.build_frozen_event_score(**args)


def test_retrieval_blocker_and_unknown_generation_proof_stay_unavailable(bundle):
    args = deepcopy(bundle[0])
    args["retrieval_state"] = RetrievalState(required=True, attempted=True, recovered=False)
    with pytest.raises(bridge.EventBridgeError, match="PUBLIC_GUARD_BLOCKED"):
        bridge.build_frozen_event_score(**args)
    args = deepcopy(bundle[0])
    args["generation_proof"] = build_candidate_generation_proof([], [], local_snapshots=["UNKNOWN"])
    with pytest.raises(bridge.EventBridgeError, match="COMPLETE_ELIGIBLE_GRAPH_REQUIRED"):
        bridge.build_frozen_event_score(**args)


def test_full_event_set_not_just_same_title_or_partial_candidates(bundle):
    args = deepcopy(bundle[0])
    state = GroundingState(post_id=args["example"]["frozen_view"]["post_id"], candidate_title="다른 작품")
    records = [EvidenceRecord(kind="candidate_preservation", candidate_title="다른 작품", supports_publish=True)]
    args["base_shadow"] = build_uncalibrated_selective_shadow(state, records, can_publish_title(state, records), generation_status="COMPLETE")
    with pytest.raises(bridge.EventBridgeError, match="BASE_CANDIDATE_SET_MISMATCH"):
        bridge.build_frozen_event_score(**args)


def test_existing_frozen_vector_retains_exact_v1_payload_and_fingerprint(bundle):
    """공통 검산 분리 전의 v1 생성식으로 기존 fixture 결과를 독립 대조한다."""
    args, _ = bundle
    record = graph_record(args)
    mapping = {r["raw_candidate_id"]: r["candidate_option_id"] for r in record["candidate_id_mapping"]}
    remapped = {mapping[r["candidate_id"]]: r["score"] for r in args["raw_receipt"]["ranked_candidates"]}
    remapped["__NIL__"] = args["raw_receipt"]["nil_score"]
    base = args["base_shadow"]
    expected = EventScoreVector.create(example_id=args["example"]["example_id"], post_id=args["example"]["frozen_view"]["post_id"],
        split="FROZEN_HOLDOUT", base_shadow=base, raw_scores=tuple(remapped[e.label] for e in base.event_probabilities),
        scorer_fingerprint=args["scorer_summary"]["scorer_sha256"], split_manifest_sha256=args["calibration_manifest"].manifest_sha256,
        generation_proof_fingerprint=args["generation_proof"].metadata_fingerprint,
        retrieval_state_fingerprint=bridge.canonical_sha256(args["retrieval_state"].to_dict()),
        feature_schema_version="candidate_reranker_nil_features_v1", feature_fingerprint=bridge.canonical_sha256({
            "schema_version": "candidate_reranker_event_bridge_v1",
            "feature_schema_sha256": args["scorer_summary"]["feature_schema_sha256"],
            "frozen_view_sha256": bridge.canonical_sha256(args["example"]["frozen_view"]),
            "source_binding_sha256": args["source_binding_sha256"]}))
    assert bridge.build_frozen_event_score(**args).to_dict() == expected.to_dict()
    assert CALIBRATION_SPLITS == ("DEV", "CALIBRATION", "FROZEN_HOLDOUT")


@pytest.fixture(scope="module")
def calibration_bundle(tmp_path_factory):
    from candidate_reranker_calibration_fixtures import build_calibration_fixture
    return build_calibration_fixture(tmp_path_factory.mktemp("calibration_event_bridge"))


def test_cal_full_batch_uses_real_local_scorer_and_independent_truth_metadata(calibration_bundle):
    from src.llm_batch.grounding.candidate_reranker_calibration_data import CalibrationFitEvent
    args = deepcopy(calibration_bundle["cal_kwargs"])
    before = deepcopy(args)
    with patch.object(Path, "open", side_effect=AssertionError("CAL bridge must not open files")):
        events = bridge.build_calibration_fit_events(**args)
    assert args == before and len(events) == 2
    assert all(isinstance(e, CalibrationFitEvent) and e.split == "CALIBRATION" for e in events)
    assert [e.truth_kind for e in events] == ["CANDIDATE", "NIL"]
    for event, row in zip(events, args["rows"]):
        assignment = next(r["assignment"] for r in args["training_manifest"]["rows"] if r["assignment"]["example_id"] == event.example_id)
        assert event.truth_label == assignment["truth_label"]
        assert event.label_provenance["artifact_sha256"] == assignment["label_provenance_sha256"]
        assert event.model_sha256 == args["scorer_summary"]["model_sha256"]
        assert event.base_model_sha256 == args["scorer_summary"]["candidate_ranker_model_sha256"]
        assert event.source_binding_sha256 == row["source_binding_sha256"]
        assert event.training_split_manifest_sha256 == args["training_manifest"]["manifest_sha256"]
        assert event.calibration_manifest_sha256 == args["calibration_manifest"].manifest_sha256
        assert event.training_split_manifest_sha256 != event.calibration_manifest_sha256
        assert row["raw_receipt"]["nil_probability"] is None
        assert CalibrationFitEvent.from_dict(json.loads(raw(event.to_dict()))) == event


@pytest.mark.parametrize("mutation", ["missing", "reorder", "duplicate", "extra", "frozen", "empty", "limit", "extra_field", "expected_missing", "expected_reorder"])
def test_cal_batch_never_filters_or_invents_expected_rows(calibration_bundle, mutation):
    args = deepcopy(calibration_bundle["cal_kwargs"])
    if mutation == "missing": args["rows"].pop()
    elif mutation == "reorder": args["rows"].reverse()
    elif mutation == "duplicate": args["rows"][1] = deepcopy(args["rows"][0])
    elif mutation == "extra": args["rows"].append(deepcopy(args["rows"][0]))
    elif mutation == "frozen":
        frozen = calibration_bundle["frozen_args"][0]
        args["rows"][0] = {key: deepcopy(frozen[key]) for key in args["rows"][0]}
    elif mutation == "empty": args["rows"] = []
    elif mutation == "limit": args["rows"] *= 129
    elif mutation == "extra_field": args["rows"][0]["truth_from_score"] = "__NIL__"
    elif mutation == "expected_missing": args["expected_example_ids"].pop()
    else: args["expected_example_ids"].reverse()
    with pytest.raises(bridge.EventBridgeError):
        bridge.build_calibration_fit_events(**args)


@pytest.mark.parametrize("mutation", ["failed", "source_changed", "source_omitted", "foreign_scope", "foreign_attempt", "foreign_model", "foreign_source_binding", "bool_score", "graph_missing"])
def test_cal_has_same_source_model_receipt_and_graph_guards(calibration_bundle, mutation):
    args = deepcopy(calibration_bundle["cal_kwargs"])
    item = args["rows"][0]
    if mutation == "failed": item["raw_receipt"]["status"] = "UNAVAILABLE"
    elif mutation == "source_changed":
        sid = args["training_manifest"]["rows"][4]["source_ids"][0]
        args["source_payloads"][sid] += b"changed"
    elif mutation == "source_omitted": item["example"]["frozen_view"]["source_view"]["fragments"].clear()
    elif mutation == "foreign_scope": item["publication_scope_id"] = "another-scope"
    elif mutation == "foreign_attempt":
        item["raw_receipt"]["binding"] = {"run_id": "other", "attempt_id": "other", "input_index": 1,
            "post_id": item["example"]["frozen_view"]["post_id"], "publication_scope_id": item["publication_scope_id"],
            "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    elif mutation == "foreign_model": item["raw_receipt"]["model_sha256"] = "0" * 64
    elif mutation == "foreign_source_binding": item["source_binding_sha256"] = args["rows"][1]["source_binding_sha256"]
    elif mutation == "bool_score": item["raw_receipt"]["nil_score"] = item["raw_receipt"]["event_logits"][-1]["score"] = False
    else: del args["evidence_payloads"][item["source_binding_sha256"]]
    if mutation in {"failed", "foreign_model", "bool_score"}:
        seal_receipt(item["raw_receipt"])
        bound_args = {**args, **item}
        bind_graph(bound_args)
        item["source_binding_sha256"] = bound_args["source_binding_sha256"]
    with pytest.raises(bridge.EventBridgeError):
        bridge.build_calibration_fit_events(**args)


def test_cal_truth_is_not_the_best_scoring_event(calibration_bundle):
    args = deepcopy(calibration_bundle["cal_kwargs"])
    item = args["rows"][0]
    receipt = item["raw_receipt"]
    receipt["nil_score"] = receipt["event_logits"][-1]["score"] = 99.0
    seal_receipt(receipt)
    bound_args = {**args, **item}
    bind_graph(bound_args)
    item["source_binding_sha256"] = bound_args["source_binding_sha256"]
    event = bridge.build_calibration_fit_events(**args)[0]
    assert event.raw_scores[-1] == 99.0 and event.truth_kind == "CANDIDATE"
    assert event.truth_label != "__NIL__"
