"""실제 로컬 R2/R3 합성 fixture로 의미 입력과 노출 결속을 검증한다."""
from copy import deepcopy
from pathlib import Path
import socket

import pytest

from llm_batch.grounding import candidate_reranker_semantic_input as si
from llm_batch.grounding import candidate_reranker_learned as learned
from test_candidate_reranker_alias_evidence import build_alias_fixture, encoded, sha, _rescore_fixture


def semantic_fixture(tmp_path, *, alias=True, text=None):
    fixture = build_alias_fixture(tmp_path)
    if text is not None:
        fixture["frozen_view"]["source_view"]["fragments"][1]["text"] = "합성후보. " + text
        _rescore_fixture(fixture, tmp_path)
    value = si.build_semantic_input(fixture["frozen_view"], retrieval_receipt=fixture["retrieval_receipt"],
        alias_evidence=fixture["call_evidence"] if alias else None,
        evidence_payloads=fixture["evidence_payloads"] if alias else None)
    return value, fixture


def training_inputs(value, fixture):
    evidence = dict(fixture["evidence_payloads"])
    raw = encoded(value)
    evidence[sha(raw)] = raw
    capture = {"schema_version": si.CAPTURE_SCHEMA, "semantic_input_sha256": sha(raw)}
    source_payloads, sources = {}, {}
    exposures = {c["corpus_candidate_id"]: {"corpus_candidate_id": c["corpus_candidate_id"],
        **{key: c[key] for key in ("work_id", "edition_id", "media_type")},
        "source_ids": [], "alias_family_ids": []} for c in value["retrieval_receipt"]["ranked_candidates"]}
    for item in si.semantic_exposure_requirements(value):
        used = [item["source_id"], item["review_source_id"]]
        for sid, digest in zip(used, [item["payload_sha256"], item["review_payload_sha256"]]):
            source_payloads[sid] = evidence[digest]
            sources[sid] = {"source_id": sid, "payload_sha256": digest, "source_group_id": sid,
                "lineage_root_id": item["lineage_root_id"], "rights_status": "SYNTHETIC_FIXTURE"}
        exposures[item["candidate_id"]] = {"corpus_candidate_id": item["candidate_id"],
            **{key: item[key] for key in ("work_id", "edition_id", "media_type")},
            "source_ids": used, "alias_family_ids": [item["alias_family_id"]]}
    row = {"source_ids": list(sources), "exposures": list(exposures.values()),
        "label_provenance": {"artifact_sha256": "a" * 64}, "role_mentions": []}
    manifest = {"data_kind": "SYNTHETIC_FIXTURE", "sources": list(sources.values())}
    return capture, row, source_payloads, evidence, manifest


def _bind(value, args):
    capture, row, payloads, evidence, manifest = args
    return si.resolve_training_semantic_input(capture, value["enriched_view"], row, payloads, evidence,
        split_manifest=manifest)


@pytest.mark.parametrize(("text", "role", "index"), [
    ("나는 아카데미 생존 갤러리를 리뷰한다.", "PRIMARY", 6),
    ("김하늘 작가의 전작은 아카데미 생존 갤러리이다.", "PREVIOUS", 7),
    ("아카데미 생존 갤러리보다 합성 별빛 도서관이 더 좋다.", "COMPARISON", 9),
])
def test_raw_producer_relations_reach_real_feature_vector(tmp_path, text, role, index):
    value, fixture = semantic_fixture(tmp_path, alias=False, text=text)
    restored = si.validate_semantic_input(value, expected_view=value["enriched_view"])
    assert restored == value
    pairs = list(zip(value["enriched_view"]["candidates"], learned._features(value["enriched_view"])))
    candidate, vector = next((c, v) for c, v in pairs if c["titles"] == ["아카데미 생존 갤러리"])
    assert vector[index] == 1 and role in {r["role"] for r in candidate["role_observations"]}
    assert value["observation"]["score_consumption_status"] == "NOT_CONSUMED_MODEL_POLICY_UNBOUND"
    assert fixture["frozen_view"]["candidates"][0]["role_observations"] == []


def test_alias_replay_is_pure_and_keeps_external_definition_separate(tmp_path, monkeypatch):
    value, fixture = semantic_fixture(tmp_path, text="나는 아생갤을 리뷰한다.")
    before = deepcopy(value)
    def forbidden(*args, **kwargs):
        raise AssertionError("입력 재생은 IO를 호출할 수 없음")
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        assert si.validate_semantic_input(value, evidence_payloads=fixture["evidence_payloads"]) == value
    assert value == before
    binding = si.semantic_exposure_requirements(value)[0]
    assert binding["source_id"] == "synthetic-alias-source"
    assert binding["review_source_id"].startswith("semantic-review:")
    assert any("아생갤" in c["aliases"] for c in value["enriched_view"]["candidates"])
    assert _bind(value, training_inputs(value, fixture)) == value


@pytest.mark.parametrize("change", ["role", "cue", "policy", "alias", "retrieval", "typed_post", "extra", "refs"])
def test_resealed_semantic_payload_is_replayed_not_trusted(tmp_path, change):
    value, fixture = semantic_fixture(tmp_path, text="나는 아생갤을 리뷰한다.")
    if change == "role":
        value["enriched_view"]["candidates"][0]["role_observations"][0]["role"] = "PREVIOUS"
    elif change == "cue":
        row = next(r for r in value["observation"]["observations"] if r["relation_cues"])
        row["relation_cues"][0]["text"] += "위조"
    elif change == "policy":
        value["observation"]["policy_sha256"] = "a" * 64
    elif change == "alias":
        value["enriched_view"]["candidates"][0]["aliases"].append("잘못된별칭")
    elif change == "retrieval":
        value["retrieval_receipt"]["post_id"] += 1
    elif change == "typed_post":
        value["original_view"]["post_id"] = str(value["original_view"]["post_id"])
    elif change == "extra":
        value["gold_label"] = "synthetic-corpus-1"
    else:
        value["alias_payload_sha256"] = []
    value["input_sha256"] = si.canonical_sha256({k: v for k, v in value.items() if k != "input_sha256"})
    with pytest.raises(ValueError):
        si.validate_semantic_input(value, evidence_payloads=fixture["evidence_payloads"])


@pytest.mark.parametrize("change", ["family", "source", "review", "lineage", "bytes", "rights", "identity", "label", "manifest"])
def test_alias_training_requires_declared_raw_source_review_and_family(tmp_path, change):
    value, fixture = semantic_fixture(tmp_path)
    args = list(training_inputs(value, fixture))
    capture, row, payloads, evidence, manifest = args
    if change == "family":
        row["exposures"][0]["alias_family_ids"] = []
    elif change == "source":
        row["source_ids"] = []
    elif change == "review":
        row["exposures"][0]["source_ids"].pop()
    elif change == "lineage":
        manifest["sources"][0]["lineage_root_id"] = "different-root"
    elif change == "bytes":
        payloads[next(iter(payloads))] = b"different"
    elif change == "rights":
        manifest["sources"][0]["rights_status"] = "UNKNOWN"
    elif change == "identity":
        row["exposures"][0]["edition_id"] = "different-edition"
    elif change == "label":
        row["label_provenance"]["artifact_sha256"] = capture["semantic_input_sha256"]
    else:
        args[-1] = None
    with pytest.raises(si.SemanticInputError):
        _bind(value, args)


def test_raw_input_duplicate_keys_and_missing_payload_are_rejected(tmp_path):
    value, fixture = semantic_fixture(tmp_path)
    raw = encoded(value)
    assert si.read_semantic_input(raw, expected_sha256=sha(raw), evidence_payloads=fixture["evidence_payloads"]) == value
    duplicate = raw[:-1] + b',"schema_version":"candidate_semantic_feature_input_v1"}'
    with pytest.raises(si.SemanticInputError, match="DUPLICATE_KEY"):
        si.read_semantic_input(duplicate, expected_sha256=sha(duplicate), evidence_payloads=fixture["evidence_payloads"])
    with pytest.raises(si.SemanticInputError, match="EVIDENCE_MISSING"):
        si.validate_semantic_input(value, evidence_payloads={})


def test_no_alias_input_still_rejects_label_artifact_and_wrong_score_view(tmp_path):
    value, fixture = semantic_fixture(tmp_path, alias=False)
    args = list(training_inputs(value, fixture))
    args[1]["label_provenance"]["artifact_sha256"] = args[0]["semantic_input_sha256"]
    with pytest.raises(si.SemanticInputError, match="LABEL_AS_FEATURE"):
        _bind(value, args)
    changed = deepcopy(value["enriched_view"])
    changed["source_view"]["fragments"][1]["text"] += "변경"
    with pytest.raises(si.SemanticInputError, match="SCORE_VIEW_MISMATCH"):
        si.validate_semantic_input(value, expected_view=changed)


@pytest.mark.parametrize("field", ["work_id", "edition_id", "media_type", "data_kind"])
def test_no_alias_resealed_r2_must_match_actual_split_exposure(tmp_path, field):
    value, fixture = semantic_fixture(tmp_path, alias=False)
    args = list(training_inputs(value, fixture))
    original_exposures = deepcopy(args[1]["exposures"])
    retrieval = deepcopy(value["retrieval_receipt"])
    if field == "data_kind":
        retrieval["policy"]["data_kind"] = "SOURCE_BACKED"
    else:
        retrieval["ranked_candidates"][0][field] = "different-known-identity"
    retrieval["observation_sha256"] = si.canonical_sha256({k: v for k, v in retrieval.items()
        if k not in {"observation_sha256", "latency_ms", "binding"}})
    from llm_batch.grounding.candidate_reranker_shadow import build_frozen_view
    original = build_frozen_view(value["original_view"]["source_view"], retrieval)
    replaced = si.build_semantic_input(original, retrieval_receipt=retrieval)
    raw = encoded(replaced)
    args[3][sha(raw)] = raw
    args[0]["semantic_input_sha256"] = sha(raw)
    args[1]["exposures"] = original_exposures
    with pytest.raises(si.SemanticInputError, match="SEMANTIC_R2_(?:IDENTITY|DATA_KIND)_MISMATCH"):
        _bind(replaced, args)
