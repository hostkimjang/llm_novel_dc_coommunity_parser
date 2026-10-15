from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket

import pytest

from llm_batch.grounding import candidate_retrieval_shadow as retrieval
from llm_batch.grounding.research_local_benchmark import _bm25_scores


def _source(ref="https://fixture.invalid/work/one", *, lineage="lineage-one", kind="SYNTHETIC_FIXTURE"):
    return {"source_ref": ref, "source_sha256": "a" * 64, "lineage_id": lineage,
            "observed_at": "2026-10-10T00:00:00+09:00",
            "rights": {"status": kind, "basis": "테스트를 위해 직접 작성한 합성 자료"}}


def _entry(candidate_id="work-one", *, title="아카데미 생존 갤러리", aliases=None, text="생존 성장 이야기",
           work_id=None, edition_id="main", media_type="WEB_NOVEL", sources=None):
    aliases = ["아생갤"] if aliases is None else aliases
    return {"corpus_candidate_id": candidate_id, "work_id": work_id or candidate_id,
            "edition_id": edition_id, "media_type": media_type, "title": title, "aliases": aliases,
            "text": text, "content_sha256": retrieval.candidate_content_sha256(title, aliases, text),
            "sources": sources or [_source()]}


def _corpus(entries=None):
    return {"schema_version": retrieval.CORPUS_SCHEMA, "corpus_id": "unit-synthetic",
            "data_kind": "SYNTHETIC_FIXTURE", "entries": entries if entries is not None else [_entry()]}


def _write(tmp_path, corpus):
    path = tmp_path / "corpus.json"
    raw = json.dumps(corpus, ensure_ascii=False, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def _load(tmp_path, corpus=None, **kwargs):
    path, sha = _write(tmp_path, corpus or _corpus())
    return retrieval.load_corpus(path, expected_sha256=sha, **kwargs)


def _view(text="아생갤", *, post_id=1, extra=None):
    fragments = [{"raw_path": "/title", "kind": "TITLE", "text": text}]
    fragments.extend(extra or [])
    return {"schema_version": retrieval.SOURCE_VIEW_SCHEMA, "post_id": post_id, "fragments": fragments}


def test_off_never_loads_even_invalid_path_or_config(monkeypatch):
    def fail_open(*args, **kwargs):
        raise AssertionError("OFF tried to access filesystem")
    monkeypatch.setattr(Path, "open", fail_open)
    assert retrieval.configure_candidate_retrieval_shadow(mode="OFF", corpus_path="absent",
                                                         expected_sha256="bad", top_k=False) is None


def test_load_once_observe_never_reads_writes_or_networks(tmp_path, monkeypatch):
    observer = _load(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("observe must be pure in-memory")
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    first = observer.observe(_view())
    second = observer.observe(_view())
    assert first["observation_sha256"] == second["observation_sha256"]
    assert first["status"] == "OK"
    assert first["ranked_candidates"][0]["corpus_candidate_id"] == "work-one"
    assert first["publication_authority"] is False
    assert first["public_apply"] is False
    assert first["central_db_write"] is False
    assert first["policy"]["source_refs_independently_verified"] is False


def test_bm25_matches_existing_benchmark_positive_scores_and_tie_break(tmp_path):
    entries = [_entry("zeta", title="작품 Alpha", aliases=["별칭"], text="alpha"),
               _entry("alpha", title="작품 Alpha", aliases=["별칭"], text="alpha"),
               _entry("zero", title="베타", aliases=[], text="무관한 본문")]
    observer = _load(tmp_path, _corpus(entries))
    receipt = observer.observe(_view("Alpha 작품 Alpha 별칭"))
    expected = _bm25_scores({"query": "Alpha 작품 Alpha 별칭", "candidates": [
        {"candidate_id": item["corpus_candidate_id"], "title": item["title"], "aliases": item["aliases"], "text": item["text"]}
        for item in entries]})
    expected = [(candidate, score) for candidate, score in expected if score > 0]
    assert [hit["corpus_candidate_id"] for hit in receipt["ranked_candidates"]] == [item[0] for item in expected]
    assert [hit["score"] for hit in receipt["ranked_candidates"]] == pytest.approx([item[1] for item in expected], rel=1e-12)
    assert receipt["counts"]["positive_candidates"] == 2
    assert receipt["policy"]["config"]["k1"] == 1.5
    assert receipt["policy"]["config"]["b"] == .75


def test_mirrors_dedup_but_same_title_distinct_work_edition_media_survive(tmp_path):
    first = _entry("mirror-b")
    mirror = deepcopy(first)
    mirror["corpus_candidate_id"] = "mirror-a"
    mirror["sources"] = [_source("https://mirror.invalid/work/one")]
    other_work = _entry("other-work")
    other_edition = _entry("other-edition", work_id=first["work_id"], edition_id="side-story")
    other_media = _entry("other-media", work_id=first["work_id"], media_type="WEBTOON")
    observer = _load(tmp_path, _corpus([first, mirror, other_work, other_edition, other_media]))
    hits = observer.observe(_view())["ranked_candidates"]
    assert len(hits) == 4
    assert observer.policy["mirror_deduplicated_count"] == 1
    mirror_hit = next(hit for hit in hits if hit["corpus_candidate_id"] == "mirror-a")
    assert mirror_hit["mirror_candidate_ids"] == ["mirror-b"]
    assert len(mirror_hit["source_refs"]) == 2
    assert {hit["edition_id"] for hit in hits} == {"main", "side-story"}
    assert {hit["media_type"] for hit in hits} == {"WEB_NOVEL", "WEBTOON"}


def test_different_lineage_is_not_mirror_inferred_from_title(tmp_path):
    first = _entry("one", work_id="same-work")
    second = _entry("two", work_id="same-work", sources=[_source(lineage="independent-declared-lineage")])
    observer = _load(tmp_path, _corpus([first, second]))
    assert observer.policy["indexed_document_count"] == 2
    assert observer.policy["mirror_deduplicated_count"] == 0


@pytest.mark.parametrize("mutation,code", [
    ("duplicate_id", "DUPLICATE_CANDIDATE_ID"),
    ("content", "CONTENT_SHA256_MISMATCH"),
    ("rights", "RIGHTS_NOT_DECLARED"),
    ("source_sha", "SHA256_INVALID"),
    ("lineage", "FIELD_INVALID"),
    ("observed", "TIMESTAMP_INVALID"),
    ("edition", "FIELD_INVALID"),
    ("media", "MEDIA_TYPE_INVALID"),
    ("schema", "CORPUS_SCHEMA_INVALID"),
    ("missing_source", "PROVENANCE_LIMIT_OR_MISSING"),
])
def test_invalid_corpus_is_rejected_with_code(tmp_path, mutation, code):
    corpus = _corpus()
    entry = corpus["entries"][0]
    if mutation == "duplicate_id":
        corpus["entries"].append(deepcopy(entry))
    elif mutation == "content":
        entry["title"] = "변조된 제목"
    elif mutation == "rights":
        entry["sources"][0]["rights"]["status"] = "UNKNOWN"
    elif mutation == "source_sha":
        entry["sources"][0]["source_sha256"] = "bad"
    elif mutation == "lineage":
        entry["sources"][0]["lineage_id"] = ""
    elif mutation == "observed":
        entry["sources"][0]["observed_at"] = "2026-10-10"
    elif mutation == "edition":
        entry["edition_id"] = None
    elif mutation == "media":
        entry["media_type"] = {"unexpected": True}
    elif mutation == "schema":
        corpus["schema_version"] = "unknown"
    else:
        entry["sources"] = []
    path, sha = _write(tmp_path, corpus)
    with pytest.raises(retrieval.CorpusError) as caught:
        retrieval.load_corpus(path, expected_sha256=sha)
    assert caught.value.code == code
    unavailable = retrieval.configure_candidate_retrieval_shadow(mode="SHADOW", corpus_path=path, expected_sha256=sha)
    receipt = unavailable.observe(_view())
    assert receipt["status"] == "UNAVAILABLE_CORPUS"
    assert receipt["reason_codes"] == [code]
    assert receipt["ranked_candidates"] == []


def test_explicit_expiry_and_byte_hash_mismatch_rejected(tmp_path):
    corpus = _corpus()
    corpus["valid_until"] = "2026-10-09T00:00:00+00:00"
    path, sha = _write(tmp_path, corpus)
    with pytest.raises(retrieval.CorpusError) as expired:
        retrieval.load_corpus(path, expected_sha256=sha, as_of=datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert expired.value.code == "CORPUS_EXPIRED"
    with pytest.raises(retrieval.CorpusError) as wrong_sha:
        retrieval.load_corpus(path, expected_sha256="0" * 64)
    assert wrong_sha.value.code == "CORPUS_SHA256_MISMATCH"


def test_empty_corpus_query_and_no_match_are_different(tmp_path):
    empty = _load(tmp_path, _corpus([]))
    assert empty.observe(_view())["status"] == "EMPTY_CORPUS"
    observer = _load(tmp_path)
    assert observer.observe(_view("!!!"))["status"] == "EMPTY_QUERY"
    missing = observer.observe(_view("외계어"))
    assert missing["status"] == "NO_MATCH"
    assert missing["ranked_candidates"] == []
    assert missing["counts"]["positive_candidates"] == 0


def test_query_fragments_cannot_join_to_create_alias_or_consume_final_fields(tmp_path):
    observer = _load(tmp_path, _corpus([_entry(aliases=["아생갤"], title="고정 작품", text="")]))
    query = _view("아생", extra=[{"raw_path": "/comments/3/content", "kind": "COMMENT", "text": "갤"}])
    before = deepcopy(query)
    receipt = observer.observe(query)
    assert receipt["status"] == "NO_MATCH"
    assert query == before
    assert [item["raw_path"] for item in receipt["source_fragments"]] == ["/title", "/comments/3/content"]
    assert all("text" not in item for item in receipt["source_fragments"])
    query["official_title"] = "아생갤"
    assert observer.observe(query)["status"] == "INVALID_SOURCE_VIEW"


@pytest.mark.parametrize("mutation,status,reason", [
    ("duplicate", "INVALID_SOURCE_VIEW", "DUPLICATE_SOURCE_PATH"),
    ("derived_path", "INVALID_SOURCE_VIEW", "SOURCE_PATH_KIND_INVALID"),
    ("large", "QUERY_LIMIT_EXCEEDED", "QUERY_CHAR_LIMIT"),
    ("many_fragments", "QUERY_LIMIT_EXCEEDED", "QUERY_FRAGMENT_LIMIT"),
    ("many_tokens", "QUERY_LIMIT_EXCEEDED", "QUERY_TOKEN_LIMIT"),
])
def test_query_bounds_and_source_paths(tmp_path, mutation, status, reason):
    observer = _load(tmp_path)
    query = _view()
    if mutation == "duplicate":
        query["fragments"].append(deepcopy(query["fragments"][0]))
    elif mutation == "derived_path":
        query["fragments"][0]["raw_path"] = "/analysis_result/identity/official_title"
    elif mutation == "large":
        query["fragments"][0]["text"] = "a" * (retrieval.MAX_QUERY_CHARS + 1)
    elif mutation == "many_fragments":
        query["fragments"] = [{"raw_path": f"/comments/{index}", "kind": "COMMENT", "text": "x"}
                              for index in range(retrieval.MAX_QUERY_FRAGMENTS + 1)]
    else:
        query["fragments"][0]["text"] = "a " * (retrieval.MAX_QUERY_TOKENS + 1)
    receipt = observer.observe(query)
    assert receipt["status"] == status
    assert receipt["reason_codes"] == [reason]
    assert receipt["post_id"] == 1
    assert receipt["query_sha256"] is None


def test_receipt_cap_preserves_only_whole_candidate_provenance(tmp_path):
    sources = [_source("https://fixture.invalid/" + str(index) + "/" + "x" * 1900, lineage="common")
               for index in range(8)]
    corpus = _corpus([_entry(f"candidate-{index}", sources=sources) for index in range(20)])
    observer = _load(tmp_path, corpus)
    receipt = observer.observe(_view())
    assert len(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()) <= retrieval.MAX_RECEIPT_BYTES
    assert receipt["status"] == "RECEIPT_LIMIT_EXCEEDED"
    assert 0 < len(receipt["ranked_candidates"]) < 20
    assert all(len(hit["source_refs"]) == 8 for hit in receipt["ranked_candidates"])
    assert receipt["counts"]["positive_candidates"] == 20
    assert receipt["counts"]["omitted_ranked_candidates"] == 20 - len(receipt["ranked_candidates"])


def test_frozen_state_and_concurrent_receipts_are_isolated(tmp_path):
    observer = _load(tmp_path, _corpus([_entry("one"), _entry("two", title="별도 작품", aliases=["다른별칭"], text="")]))
    with pytest.raises(FrozenInstanceError):
        observer._top_k = 1
    with pytest.raises(TypeError):
        observer._postings["injected"] = ()
    policy = observer.policy
    policy["config"]["top_k"] = 0
    before = observer.observe(_view())
    before["ranked_candidates"][0]["source_refs"][0]["lineage_id"] = "changed"
    with ThreadPoolExecutor(max_workers=2) as executor:
        outputs = list(executor.map(observer.observe, [_view("아생갤", post_id=1), _view("다른별칭", post_id=2)]))
    assert [value["post_id"] for value in outputs] == [1, 2]
    assert [value["ranked_candidates"][0]["corpus_candidate_id"] for value in outputs] == ["one", "two"]
    assert outputs[0]["ranked_candidates"][0]["source_refs"][0]["lineage_id"] == "lineage-one"
    assert observer.policy["config"]["top_k"] == 20


@pytest.mark.parametrize("kwargs", [{"top_k": True}, {"top_k": 0}, {"k1": float("nan")}, {"b": 2}])
def test_invalid_config_is_not_silently_defaulted(tmp_path, kwargs):
    path, sha = _write(tmp_path, _corpus())
    with pytest.raises(retrieval.CorpusError) as caught:
        retrieval.load_corpus(path, expected_sha256=sha, **kwargs)
    assert caught.value.code == "CONFIG_INVALID"


def test_source_backed_requires_explicit_rights_and_never_claims_independent_proof(tmp_path):
    corpus = _corpus([_entry(sources=[_source(kind="REUSE_PERMITTED")])])
    corpus["data_kind"] = "SOURCE_BACKED"
    observer = _load(tmp_path, corpus)
    assert observer.policy["data_kind"] == "SOURCE_BACKED"
    assert observer.policy["source_refs_independently_verified"] is False
    assert observer.policy["freshness_status"] == "NO_EXPIRY_POLICY_DECLARED"

