"""새 입력의 실제 R2/고정 NIL 점수→원문 bytes graph. 실행은 root 묶음 전용."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket

import pytest

from llm_batch.grounding import candidate_retrieval_shadow as retrieval
from llm_batch.grounding import candidate_reranker_shadow as shadow
from llm_batch.grounding import candidate_reranker_inference_graph as graph
from llm_batch.grounding.candidate_reranker_capture import build_capture
from test_candidate_reranker_shadow import _nil_scorer, _semantic_scorer


def raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def _capture(scorer, source_view, receipt):
    frozen = shadow.build_frozen_view(source_view, receipt)
    kwargs = {}
    if scorer.summary().get("semantic_input_required"):
        from llm_batch.grounding.candidate_reranker_semantic_input import build_semantic_input
        semantic = build_semantic_input(frozen, retrieval_receipt=receipt)
        frozen = semantic["enriched_view"]
        kwargs = {"semantic_input": semantic, "evidence_payloads": {}}
    scored = scorer.score(frozen, **kwargs)
    return build_capture(frozen, scored, receipt, scorer.summary(), **kwargs)


def build_inference_graph_fixture(scorer, *, top_k=20, post_id=99001, text=None, mirror=False,
                                  data_kind="SYNTHETIC_FIXTURE"):
    """공용 factory. 학습 자료에 배정하지 않은 typed post와 실제 source bytes를 만든다.

    반환: capture/corpus_snapshot/source_payloads/scorer/retrieval/source_view/corpus.
    전달된 고정 scorer를 한 번 호출하며 새로운 학습이나 파일 작업은 하지 않는다.
    """
    entries, payloads = [], {}
    for cid, wid, edition, media in (("r2-one", "work-one", "main", "WEB_NOVEL"),
                                    ("r2-two", "work-two", "main", "WEB_NOVEL"),
                                    ("r2-three", "work-one", "revised", "WEBTOON")):
        title = "합성 바다 기록"
        content = f"{title}의 {cid} 원시 소개 자료"
        payload = content.encode("utf-8")
        digest = sha(payload); payloads[digest] = payload
        entries.append({"corpus_candidate_id": cid, "work_id": wid, "edition_id": edition,
            "media_type": media, "title": title, "aliases": [], "text": content,
            "content_sha256": retrieval.candidate_content_sha256(title, [], content),
            "sources": [{"source_ref": f"https://fixture.invalid/{cid}", "source_sha256": digest,
                "lineage_id": f"declared-{cid}", "observed_at": "2026-10-01T00:00:00Z",
                "rights": {"status": "SYNTHETIC_FIXTURE" if data_kind == "SYNTHETIC_FIXTURE" else "REUSE_PERMITTED",
                           "basis": "단위시험에서 만든 선언. 실제 권리 검증이 아님"}}]})
    if mirror:
        copy = deepcopy(entries[0]); copy["corpus_candidate_id"] = "r2-one-mirror"
        copy["sources"][0]["source_ref"] += "/mirror"
        entries.append(copy)
    corpus = {"schema_version": retrieval.CORPUS_SCHEMA, "corpus_id": "unseen-inference-fixture",
              "data_kind": data_kind, "entries": entries}
    snapshot = raw(corpus)
    observer = retrieval.load_corpus_bytes(snapshot, expected_sha256=sha(snapshot), top_k=top_k)
    source = {"schema_version": retrieval.SOURCE_VIEW_SCHEMA, "post_id": post_id, "fragments": [
        {"raw_path": "/title", "kind": "TITLE", "text": text if text is not None else "나는 합성 바다 기록을 리뷰한다."}]}
    receipt = observer.observe(source)
    captured = _capture(scorer, source, receipt)
    return {"capture": captured, "corpus_snapshot": snapshot, "source_payloads": payloads,
            "scorer": scorer, "retrieval": observer, "source_view": source, "corpus": corpus}


def arguments(value):
    return {key: value[key] for key in ("capture", "corpus_snapshot", "source_payloads")}


@pytest.fixture(scope="module")
def scorer(tmp_path_factory):
    return _nil_scorer(tmp_path_factory.mktemp("inference-nil"))[0]


@pytest.fixture(scope="module")
def fixture(scorer):
    return build_inference_graph_fixture(scorer)


def test_bytes_loader_matches_existing_file_loader_and_does_not_read(tmp_path, fixture, monkeypatch):
    path = tmp_path / "corpus.json"; path.write_bytes(fixture["corpus_snapshot"])
    file_observer = retrieval.load_corpus(path, expected_sha256=sha(fixture["corpus_snapshot"]), top_k=7, k1=1.2, b=.6)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("bytes loader read a file"))
    memory = retrieval.load_corpus_bytes(fixture["corpus_snapshot"], expected_sha256=sha(fixture["corpus_snapshot"]), top_k=7, k1=1.2, b=.6)
    assert memory.summary() == file_observer.summary()
    assert memory.observe(fixture["source_view"])["observation_sha256"] == file_observer.observe(fixture["source_view"])["observation_sha256"]


@pytest.mark.parametrize("fault,reason", [("pin", "CORPUS_SHA256_MISMATCH"), ("type", "CORPUS_BYTES_REQUIRED"),
    ("limit", "CORPUS_BYTE_LIMIT"), ("duplicate", "DUPLICATE_JSON_KEY"), ("expiry", "CORPUS_EXPIRED")])
def test_bytes_loader_keeps_strict_pins_schema_limits_and_expiry(fixture, fault, reason):
    snapshot = fixture["corpus_snapshot"]; digest = sha(snapshot)
    if fault == "pin": digest = "0" * 64
    elif fault == "type": snapshot = bytearray(snapshot)
    elif fault == "limit": snapshot = b" " * (retrieval.MAX_CORPUS_BYTES + 1); digest = sha(snapshot)
    elif fault == "duplicate": snapshot = b'{"entries":[],"entries":[]}'; digest = sha(snapshot)
    else:
        value = deepcopy(fixture["corpus"]); value["valid_until"] = "2026-10-01T00:00:00Z"
        snapshot = raw(value); digest = sha(snapshot)
    with pytest.raises(retrieval.CandidateRetrievalShadowError) as exc:
        retrieval.load_corpus_bytes(snapshot, expected_sha256=digest, as_of=datetime(2026,10,10,tzinfo=timezone.utc))
    assert exc.value.code == reason


def test_actual_unseen_r2_nil_graph_keeps_typed_ids_sources_and_no_truth(fixture, monkeypatch):
    args = arguments(fixture); before = deepcopy(args)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("graph filesystem"))
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("graph network"))
    monkeypatch.setattr(type(fixture["scorer"]), "score", lambda *a, **k: pytest.fail("graph rescored model"))
    value = graph.build_inference_graph(**args)
    assert graph.validate_inference_graph(value, **args) == value
    assert value["status"] == "COMPLETE" and value["post_id"] == 99001 and type(value["post_id"]) is int
    assert value["labels"] == [c["candidate_id"] for c in value["candidates"]] + ["__NIL__"]
    assert value["raw_scores"] == [e["score"] for e in args["capture"]["raw_receipt"]["event_logits"]]
    assert len(value["candidates"]) == 3  # 동명이어도 work/edition/media를 합치지 않는다.
    assert value["score_provenance"] == "CAPTURE_STRUCTURAL_BINDING_ONLY_MODEL_REPLAY_REQUIRED"
    assert value["generation_proof"]["source_bytes_verified"] is True
    assert value["generation_proof"]["source_claims_independently_verified"] is False
    assert value["truth_status"] == "UNJUDGED_NOT_ASSIGNED" and value["nil_probability"] is None
    assert value["probability_status"] == "NOT_AVAILABLE_UNCALIBRATED"
    assert not any(value[k] for k in ("publication_authority", "public_apply", "central_db_write", "action_applied"))
    assert not any(k in value for k in ("split", "truth_label", "matched_candidate_ids", "publication_scope_id"))
    assert args == before


def test_actual_semantic_nil_capture_uses_the_same_graph_contract(tmp_path):
    semantic_scorer, _, _ = _semantic_scorer(tmp_path, head=True)
    fixture = build_inference_graph_fixture(semantic_scorer, post_id="unseen-string-id")
    value = graph.build_inference_graph(**arguments(fixture))
    assert value["status"] == "COMPLETE" and type(value["post_id"]) is str
    assert value["semantic_input_sha256"] == fixture["capture"]["semantic_input"]["input_sha256"]
    assert value["scorer_summary"]["semantic_input_required"] is True


def test_mirror_identity_and_original_source_bytes_are_retained(scorer):
    fixture = build_inference_graph_fixture(scorer, mirror=True)
    value = graph.build_inference_graph(**arguments(fixture))
    one = next(c for c in value["candidates"] if c["candidate_id"] == "r2-one")
    assert one["mirror_candidate_ids"] == ["r2-one-mirror"] and len(one["source_refs"]) == 2
    assert value["generation_proof"]["input_entry_count"] == 4
    assert value["generation_proof"]["indexed_document_count"] == 3


@pytest.mark.parametrize("fault,reason", [("missing", "RETRIEVED_SOURCE_BYTES_MISSING"),
    ("source_raw", "SOURCE_PAYLOAD_SHA_MISMATCH"), ("corpus_raw", "CORPUS_SHA_MISMATCH"),
    ("wrong_map_type", "SOURCE_PAYLOAD_MAP_INVALID")])
def test_missing_or_changed_raw_bytes_fail_closed(fixture, fault, reason):
    args = deepcopy(arguments(fixture))
    if fault == "missing": args["source_payloads"].popitem()
    elif fault == "source_raw": args["source_payloads"][next(iter(args["source_payloads"]))] += b"changed"
    elif fault == "corpus_raw": args["corpus_snapshot"] += b" "
    else: args["source_payloads"] = []
    with pytest.raises(graph.InferenceGraphError, match=reason): graph.build_inference_graph(**args)


def test_source_backed_declarations_do_not_silently_change_synthetic_model_kind(scorer):
    fixture = build_inference_graph_fixture(scorer, data_kind="SOURCE_BACKED")
    with pytest.raises(graph.InferenceGraphError, match="MODEL_CORPUS_DATA_KIND_MISMATCH"):
        graph.build_inference_graph(**arguments(fixture))


@pytest.mark.parametrize("state,expected", [("truncated", "TRUNCATED"), ("empty", "EMPTY"), ("backend_error", "NOT_AVAILABLE")])
def test_non_scoring_graphs_keep_terminal_and_never_invent_nil(scorer, state, expected, monkeypatch):
    if state == "backend_error":
        from llm_batch.grounding import candidate_reranker_nil_learned as nil
        monkeypatch.setattr(nil, "score_event_logits", lambda *a, **k: (_ for _ in ()).throw(ValueError("fail")))
    fixture = build_inference_graph_fixture(scorer, top_k=1 if state == "truncated" else 20,
        text="검색사전에없는단어" if state == "empty" else None)
    value = graph.build_inference_graph(**arguments(fixture))
    assert value["status"] == expected and value["labels"] == value["raw_scores"] == []
    assert value["nil_probability"] is None and value["selected_candidate_id"] is None


@pytest.mark.parametrize("field", ["work_id", "edition_id", "media_type", "content_sha256", "source_refs"])
def test_resealed_r2_identity_provenance_must_replay_the_actual_corpus(fixture, field):
    args = arguments(fixture)
    receipt = deepcopy(args["capture"]["retrieval_receipt"])
    hit = receipt["ranked_candidates"][0]
    if field == "source_refs": hit[field][0]["lineage_id"] = "resealed-other-lineage"
    elif field == "content_sha256": hit[field] = "e" * 64
    elif field == "media_type": hit[field] = "GAME"
    else: hit[field] = "resealed-other-id"
    receipt["observation_sha256"] = graph.canonical_sha256({k:v for k,v in receipt.items() if k not in ("observation_sha256", "latency_ms", "binding")})
    args["capture"] = _capture(fixture["scorer"], fixture["source_view"], receipt)
    with pytest.raises(graph.InferenceGraphError, match="R2_RECEIPT_REPLAY_MISMATCH"):
        graph.build_inference_graph(**args)


@pytest.mark.parametrize("fault", ["post_id_type", "candidate_order", "source_bytes", "authority", "proof", "score", "extra_key"])
def test_graph_self_reseal_is_not_a_substitute_for_replay(fixture, fault):
    args = arguments(fixture); value = graph.build_inference_graph(**args)
    if fault == "post_id_type": value["post_id"] = str(value["post_id"])
    elif fault == "candidate_order": value["candidates"].reverse()
    elif fault == "source_bytes": value["source_payloads_base64"][next(iter(value["source_payloads_base64"]))] = "eA=="
    elif fault == "authority": value["public_apply"] = True
    elif fault == "proof":
        value["generation_proof"]["positive_candidates"] += 1
        value["generation_proof"]["proof_sha256"] = graph.canonical_sha256({k:v for k,v in value["generation_proof"].items() if k != "proof_sha256"})
    elif fault == "score": value["raw_scores"][0] += 1
    else: value["invented"] = True
    value["graph_sha256"] = graph.canonical_sha256({k:v for k,v in value.items() if k != "graph_sha256"})
    with pytest.raises(graph.InferenceGraphError, match="INFERENCE_GRAPH_REPLAY_MISMATCH"):
        graph.validate_inference_graph(value, **args)


def test_reused_corpus_queries_are_isolated_and_deterministic(scorer):
    rows = [build_inference_graph_fixture(scorer, post_id=99010+i) for i in range(3)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        graphs = list(pool.map(lambda row: graph.build_inference_graph(**arguments(row)), rows))
    assert [v["post_id"] for v in graphs] == [99010,99011,99012]
    assert len({v["graph_sha256"] for v in graphs}) == 3
    for row,value in zip(rows,graphs):
        assert graph.validate_inference_graph(value, **arguments(row)) == value
