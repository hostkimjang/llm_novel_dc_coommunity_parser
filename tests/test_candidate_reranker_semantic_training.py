"""실제 R2/의미 producer→TRAIN/NIL 특징의 합성 계약. 실행은 root 묶음에서만."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_batch.grounding import candidate_reranker_learned as learned
from llm_batch.grounding import candidate_reranker_nil_learned as nil
from llm_batch.grounding import candidate_reranker_semantic_input as semantic
from llm_batch.grounding import candidate_reranker_alias_evidence as aliases
from llm_batch.grounding import candidate_retrieval_shadow as retrieval
from llm_batch.grounding import candidate_reranker_shadow as shadow
from llm_batch.grounding import reranker_training_split as split
from tests.test_candidate_reranker_learned import training_fixture
from tests.test_candidate_reranker_alias_evidence import build_alias_fixture
from tests.test_candidate_retrieval_shadow import _entry, _corpus


def _raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _span(sid, raw, text, path="/content"):
    encoded = text.encode("utf-8")
    start = raw.index(encoded)
    return {"source_id": sid, "raw_path": path, "utf8_byte_span_start": start,
            "utf8_byte_span_end": start + len(encoded), "text": text, "span_sha256": _sha(encoded)}


def _capture(bundle, example, artifact):
    manifest, _, evidence, examples = bundle
    row = next(r for r in manifest["rows"] if r["assignment"]["example_id"] == example["example_id"])
    raw = _raw(artifact)
    evidence[_sha(raw)] = raw
    capture = {"schema_version": learned.CAPTURE_SCHEMA_V2, "stage": "PRE_SELECTION",
        "feature_authority": "SOURCE_OBSERVATION_NOT_GOLD", "example_id": example["example_id"],
        "post_id": row["assignment"]["post_id"], "binding": row["binding"],
        "source_spans_sha256": learned.canonical_sha256(row["source_spans"]),
        "candidate_set_fingerprint": row["assignment"]["candidate_set_fingerprint"],
        "frozen_view_sha256": learned.canonical_sha256(example["frozen_view"]),
        "candidate_text_bindings_sha256": learned.canonical_sha256(example["candidate_text_bindings"]),
        "semantic_input_sha256": _sha(raw)}
    encoded = _raw(capture)
    evidence[_sha(encoded)] = encoded
    example["capture_sha256"] = _sha(encoded)
    return capture


def semantic_training_fixture(tmp_path, *, with_alias=False):
    """공용 factory: 실제 producer의 TRAIN 후보/NIL 두 행, 나머지 split 보존.

    반환은 기존 (manifest, sources, evidence, examples) 네 항목이다.
    선택적 별칭은 실제 R3 builder와 R2를 거쳐 원문·review·family 노출을 선언한다.
    """
    bundle = training_fixture(include_nil=True)
    manifest, payloads, evidence, examples = bundle
    for index, example in enumerate(examples):
        row = next(r for r in manifest["rows"] if r["assignment"]["example_id"] == example["example_id"])
        sid = row["source_ids"][0]
        source = next(s for s in manifest["sources"] if s["source_id"] == sid)
        use_alias = with_alias and index == 0
        alias_fixture = build_alias_fixture(tmp_path / "alias") if use_alias else None
        titles = ([entry["title"] for entry in alias_fixture["corpus"]["entries"]] if use_alias
                  else [candidate["titles"][0] for candidate in example["frozen_view"]["candidates"]])
        text = (f"나는 아생갤을 리뷰한다. {titles[0]} 안내. {titles[1]}은 김하늘 작가의 전작이다."
                if use_alias else f"나는 {titles[0]}를 리뷰한다. {titles[1]}은 김하늘 작가의 전작이다.")
        raw = text.encode("utf-8")
        payloads[sid] = raw
        source["payload_sha256"] = _sha(raw)
        row["source_spans"] = [_span(sid, raw, text)]
        row["assignment"]["content_fingerprint"] = split.canonical_sha256(row["source_spans"])
        entries = alias_fixture["corpus"]["entries"] if use_alias else [
            _entry(e["corpus_candidate_id"], title=title, aliases=[], text="리뷰한다 전작이다",
                   work_id=e["work_id"], edition_id=e["edition_id"])
            for e, title in zip(row["exposures"], titles)]
        for e, entry, bridge in zip(row["exposures"], entries, row["r2_id_bridges"]):
            e.update({key: entry[key] for key in ("corpus_candidate_id", "work_id", "edition_id", "media_type")})
            bridge["corpus_candidate_id"] = e["corpus_candidate_id"]
        # 원문에 실제 나온 제목의 annotation과 특징 관측은 별도 자료다.
        label_raw = _raw({"schema_version": "synthetic_semantic_training_label", "titles": titles,
                          "truth_kind": row["assignment"]["truth_kind"], "roles": ["PRIMARY", "PREVIOUS"]})
        label_sha = _sha(label_raw)
        evidence[label_sha] = label_raw
        row["label_provenance"]["artifact_sha256"] = label_sha
        row["assignment"]["label_provenance_sha256"] = label_sha
        for mention, title, role, bridge in zip(row["role_mentions"], titles, ("PRIMARY", "PREVIOUS"), row["r2_id_bridges"]):
            mention.update(source_span=_span(sid, raw, title), roles=[role])
            mention["provenance"]["artifact_sha256"] = label_sha
            bridge["provenance_sha256"] = label_sha
        corpus = alias_fixture["corpus"] if use_alias else _corpus(entries)
        folder = tmp_path / ("corpus-" + str(index))
        folder.mkdir(parents=True)
        path = folder / "corpus.json"
        path.write_bytes(_raw(corpus))
        r2_source = {"schema_version": retrieval.SOURCE_VIEW_SCHEMA, "post_id": row["assignment"]["post_id"],
                     "fragments": [{"raw_path": "/content", "kind": "BODY", "text": text}]}
        receipt = retrieval.load_corpus(path, expected_sha256=_sha(path.read_bytes())).observe(r2_source)
        original = shadow.build_frozen_view(r2_source, receipt)
        assert original["generation_status"] == "COMPLETE" and len(original["candidates"]) == 2
        alias_evidence = None
        if use_alias:
            evidence.update(alias_fixture["evidence_payloads"])
            alias_evidence = {**alias_fixture["alias_evidence"], "retrieval_receipt": receipt,
                "community_source_view": aliases.build_alias_community_source_view(r2_source,
                    community={"value": "synthetic-novel-community", "status": "EXPLICIT", "source_path": "/gallery_id"},
                    as_of={"value": "2026-10-08T00:00:00Z", "status": "EXPLICIT", "source_path": "/created_at"})}
        artifact = semantic.build_semantic_input(original, retrieval_receipt=receipt,
            alias_evidence=alias_evidence, evidence_payloads=evidence)
        requirements = semantic.semantic_exposure_requirements(artifact)
        if use_alias:
            assert len(requirements) == 1
        by_id = {e["corpus_candidate_id"]: e for e in row["exposures"]}
        for required in requirements:
            exposure = by_id[required["candidate_id"]]
            exposure["alias_family_ids"].append(required["alias_family_id"])
            for added_sid, digest in ((required["source_id"], required["payload_sha256"]),
                                      (required["review_source_id"], required["review_payload_sha256"])):
                payloads[added_sid] = evidence[digest]
                manifest["sources"].append({"source_id": added_sid, "payload_sha256": digest,
                    "source_group_id": "semantic-group:" + required["lineage_root_id"],
                    "lineage_root_id": required["lineage_root_id"], "rights_status": "SYNTHETIC_FIXTURE"})
                row["source_ids"].append(added_sid)
                exposure["source_ids"].append(added_sid)
        source_table = {s["source_id"]: s for s in manifest["sources"]}
        row["assignment"]["source_group_fingerprint"] = split.canonical_sha256(sorted({
            source_table[key]["source_group_id"] for key in row["source_ids"]}))
        row["assignment"]["candidate_set_fingerprint"] = split.canonical_sha256(row["exposures"])
        if row["assignment"]["truth_kind"] == "CANDIDATE":
            row["assignment"]["gold_work_fingerprint"] = split.canonical_sha256(row["exposures"][0]["work_id"])
        example["frozen_view"] = artifact["enriched_view"]
        example["candidate_text_bindings"] = []
        for candidate in example["frozen_view"]["candidates"]:
            alias_spans = []
            for surface in candidate["aliases"]:
                required = next(r for r in requirements if r["candidate_id"] == candidate["candidate_id"] and r["alias"] == surface)
                alias_spans.append(_span(required["source_id"], payloads[required["source_id"]], surface))
            example["candidate_text_bindings"].append({"candidate_id": candidate["candidate_id"],
                "titles": [_span(sid, raw, title) for title in candidate["titles"]], "aliases": alias_spans})
        _capture(bundle, example, artifact)
    manifest["manifest_sha256"] = split.seal_manifest(manifest)["manifest_sha256"]
    return bundle


def _artifact(bundle, index=0):
    capture = json.loads(bundle[2][bundle[3][index]["capture_sha256"]])
    return json.loads(bundle[2][capture["semantic_input_sha256"]])


def _train(bundle, *, head=False):
    module = nil if head else learned
    config = {"base": {"epochs": 4}, "nil_head": {"epochs": 4}} if head else {"epochs": 4}
    return module.train_model(bundle[0], source_payloads=bundle[1], evidence_payloads=bundle[2],
        examples=bundle[3], config=config, feature_schema=module.FEATURE_SCHEMA_V2)


@pytest.mark.parametrize("head", [False, True])
def test_real_preselection_producer_enters_train_features_and_frozen_nil_base(tmp_path, head):
    bundle = semantic_training_fixture(tmp_path)
    before = deepcopy(bundle)
    with patch.object(Path, "open", side_effect=AssertionError("pure training must not read files")):
        result = _train(bundle, head=head)
    model, report = result["model"], result["training_report"]
    module = nil if head else learned
    assert model["schema_version"] == module.MODEL_SCHEMA_V2
    assert model["feature_schema"] == module.FEATURE_SCHEMA_V2
    assert model["training_binding"]["semantic_feature_contract_sha256"] == semantic.FEATURE_CONTRACT_SHA256
    assert model["training_binding"]["semantic_inputs_sha256"] == learned.canonical_sha256(sorted(
        _artifact(bundle, index)["input_sha256"] for index in range(len(bundle[3]))))
    assert bundle == before and report["optimization_split"] == "TRAIN"
    assert report["actual_performance_evaluated"] is False and report["formal_kpi_status"] == "NOT_ESTIMABLE"
    artifact = _artifact(bundle)
    assert artifact["observation"]["counts"]["primary"] == artifact["observation"]["counts"]["previous"] == 1
    view = artifact["enriched_view"]
    matrix = learned._features(view)
    assert sum(v[learned.FEATURE_NAMES.index("role_primary")] for v in matrix) == 1
    assert sum(v[learned.FEATURE_NAMES.index("role_previous")] for v in matrix) == 1
    if head:
        base = _train(bundle)["model"]
        assert model["base_model"] == base and report["base_parameters_updated"] is False
        events = nil.score_event_logits(model, view, semantic_input=artifact, evidence_payloads=bundle[2])
        assert events["labels"] == [c["candidate_id"] for c in view["candidates"]] + ["__NIL__"]
        assert events["nil_probability"] is events["selected_label"] is None
    else:
        assert learned.score_view(model, view, semantic_input=artifact, evidence_payloads=bundle[2])
        weights = model["weights"]
        assert weights[learned.FEATURE_NAMES.index("role_primary")] != 0
        assert weights[learned.FEATURE_NAMES.index("role_previous")] != 0


@pytest.mark.parametrize("fault", ["missing", "policy", "role", "view", "raw", "capture_version"])
def test_semantic_training_replays_resealed_input_before_optimizer(tmp_path, fault):
    bundle = semantic_training_fixture(tmp_path)
    example, artifact = bundle[3][0], _artifact(bundle)
    capture = json.loads(bundle[2][example["capture_sha256"]])
    if fault == "missing":
        bundle[2].pop(capture["semantic_input_sha256"])
    elif fault == "raw":
        bundle[2][capture["semantic_input_sha256"]] += b"changed"
    elif fault == "capture_version":
        capture["schema_version"] = learned.CAPTURE_SCHEMA
        raw = _raw(capture)
        bundle[2][_sha(raw)] = raw
        example["capture_sha256"] = _sha(raw)
    else:
        if fault == "policy":
            artifact["contract_sha256"] = "0" * 64
        elif fault == "role":
            artifact["enriched_view"]["candidates"][0]["role_observations"][0]["role"] = "UNKNOWN"
            example["frozen_view"] = artifact["enriched_view"]
        else:
            example["frozen_view"]["candidates"][0]["aliases"] = ["unproved"]
        artifact["input_sha256"] = learned.canonical_sha256({k: v for k, v in artifact.items() if k != "input_sha256"})
        _capture(bundle, example, artifact)
    with patch.object(learned, "_loss", side_effect=AssertionError("optimizer must not run")):
        with pytest.raises(ValueError):
            _train(bundle)


@pytest.mark.parametrize("head", [False, True])
def test_alias_features_require_raw_definition_review_and_alias_family_exposure(tmp_path, head):
    bundle = semantic_training_fixture(tmp_path, with_alias=True)
    model = _train(bundle, head=head)["model"]
    artifact = _artifact(bundle)
    assert any(c["aliases"] == ["아생갤"] for c in artifact["enriched_view"]["candidates"])
    assert any(v[learned.FEATURE_NAMES.index("alias_substring")] == 1 for v in learned._features(artifact["enriched_view"]))
    scorer = nil.score_event_logits if head else learned.score_view
    assert scorer(model, artifact["enriched_view"], semantic_input=artifact, evidence_payloads=bundle[2])
    base = model["base_model"] if head else model
    assert base["weights"][learned.FEATURE_NAMES.index("alias_substring")] != 0
    if head:
        assert model["weights"][nil.FEATURE_NAMES.index("max_alias_substring")] != 0
    required = semantic.semantic_exposure_requirements(artifact)[0]
    row = next(r for r in bundle[0]["rows"] if r["assignment"]["example_id"] == bundle[3][0]["example_id"])
    exposure = next(e for e in row["exposures"] if e["corpus_candidate_id"] == required["candidate_id"])
    exposure["alias_family_ids"].remove(required["alias_family_id"])
    bundle[0]["manifest_sha256"] = split.seal_manifest(bundle[0])["manifest_sha256"]
    with pytest.raises(ValueError, match="SEMANTIC_ALIAS_FAMILY_NOT_EXPOSED"):
        _train(bundle, head=head)


@pytest.mark.parametrize("fault", ["review_source", "lineage", "cross_split_family"])
def test_actual_alias_training_rejects_incomplete_or_leaking_exposure_before_optimizer(tmp_path, fault):
    bundle = semantic_training_fixture(tmp_path, with_alias=True)
    artifact = _artifact(bundle)
    required = semantic.semantic_exposure_requirements(artifact)[0]
    row = next(r for r in bundle[0]["rows"] if r["assignment"]["example_id"] == bundle[3][0]["example_id"])
    exposure = next(e for e in row["exposures"] if e["corpus_candidate_id"] == required["candidate_id"])
    if fault == "review_source":
        exposure["source_ids"].remove(required["review_source_id"])
    elif fault == "lineage":
        source = next(s for s in bundle[0]["sources"] if s["source_id"] == required["review_source_id"])
        source["lineage_root_id"] = "different-declared-lineage"
    else:
        other = next(r for r in bundle[0]["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT")
        other["exposures"][0]["alias_family_ids"].append(required["alias_family_id"])
    bundle[0]["manifest_sha256"] = split.seal_manifest(bundle[0])["manifest_sha256"]
    with patch.object(learned, "_loss", side_effect=AssertionError("optimizer must not run")):
        with pytest.raises(ValueError):
            _train(bundle, head=True)


@pytest.mark.parametrize("head", [False, True])
def test_semantic_features_do_not_use_role_labels_or_nontrain_labels(tmp_path, head):
    bundle = semantic_training_fixture(tmp_path)
    original = _train(bundle, head=head)["model"]
    for row in bundle[0]["rows"]:
        for mention in row["role_mentions"]:
            mention["roles"] = ["COMPARISON"]
    bundle[0]["manifest_sha256"] = split.seal_manifest(bundle[0])["manifest_sha256"]
    changed = _train(bundle, head=head)["model"]
    assert changed["weights"] == original["weights"]
    assert changed["training_binding"]["semantic_inputs_sha256"] == original["training_binding"]["semantic_inputs_sha256"]
    assert changed["training_binding"]["split_manifest_sha256"] != original["training_binding"]["split_manifest_sha256"]
    if head:
        assert changed["base_model"]["weights"] == original["base_model"]["weights"]


@pytest.mark.parametrize("head", [False, True])
def test_v2_scoring_requires_replay_and_v1_rejects_semantic_arguments(tmp_path, head):
    bundle = semantic_training_fixture(tmp_path)
    model = _train(bundle, head=head)["model"]
    artifact, view = _artifact(bundle), bundle[3][0]["frozen_view"]
    scorer = nil.score_event_logits if head else learned.score_view
    with pytest.raises(ValueError, match="SEMANTIC_INPUT_REQUIRED"):
        scorer(model, view)
    forged = deepcopy(artifact)
    forged["observation"]["counts"]["primary"] += 1
    forged["input_sha256"] = learned.canonical_sha256({k: v for k, v in forged.items() if k != "input_sha256"})
    with pytest.raises(ValueError):
        scorer(model, view, semantic_input=forged, evidence_payloads=bundle[2])
    old = training_fixture(include_nil=True)
    module = nil if head else learned
    config = {"base": {"epochs": 2}, "nil_head": {"epochs": 2}} if head else {"epochs": 2}
    legacy = module.train_model(old[0], source_payloads=old[1], evidence_payloads=old[2], examples=old[3], config=config)["model"]
    assert legacy["schema_version"] == module.MODEL_SCHEMA
    with pytest.raises(ValueError, match="V1_SEMANTIC_INPUT_FORBIDDEN"):
        scorer(legacy, old[3][0]["frozen_view"], semantic_input=artifact)


@pytest.mark.parametrize("head", [False, True])
@pytest.mark.parametrize("fault", ["feature_contract", "binding_pin", "downgrade"])
def test_resealed_semantic_models_cannot_change_policy_or_downgrade(tmp_path, head, fault):
    model = _train(semantic_training_fixture(tmp_path), head=head)["model"]
    module = nil if head else learned
    if fault == "feature_contract":
        model["feature_contract"]["stage"] = "POST_SELECTION"
        model["feature_contract_sha256"] = learned.canonical_sha256(model["feature_contract"])
    elif fault == "binding_pin":
        model["training_binding"]["semantic_feature_contract_sha256"] = "0" * 64
    else:
        model["schema_version"] = module.MODEL_SCHEMA
        model["feature_schema"] = module.FEATURE_SCHEMA
    model["model_sha256"] = learned.canonical_sha256({k: v for k, v in model.items() if k != "model_sha256"})
    with pytest.raises(ValueError):
        module.validate_model(model)
