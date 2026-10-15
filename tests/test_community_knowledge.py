"""Synthetic local snapshots only; no real knowledge-quality or model claims."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from llm_batch.grounding import community_knowledge as ck


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def byte_sha(value):
    return hashlib.sha256(value).hexdigest()


def seal(row):
    row["row_content_sha256"] = ck.row_content_sha256(row)
    return row


def source_and_candidate(index=1, *, surface="아생갤", definition="합성 작품 약어", sense=None, community="community-a"):
    statement = "'" + surface + "'은 " + definition + "를 뜻한다."
    payload = statement.encode("utf-8")
    sid = "capture-" + str(index)
    basis = b"SYNTHETIC TEST DATA; NO ACTUAL RIGHTS ASSERTION"
    source = {"source_id": sid, "source_ref": "fixture://" + sid, "payload_ref": "payloads/" + sid + ".txt",
              "payload_byte_sha256": byte_sha(payload), "capture_profile": "COMMUNITY_STRUCTURED",
              "capture_version": "normalized-community-explicit-statement-lines-v1", "normalization_version": "utf8_identity_v1",
              "source_published_at": "2026-10-01T00:00:00Z", "source_modified_at": None,
              "captured_at": "2026-10-02T00:00:00Z", "available_at": "2026-10-02T00:00:00Z", "time_unknown_reason": None,
              "community_scope": [community], "lineage_root_id": "root-" + str(index), "parent_id": None,
              "derivation_kind": "ORIGINAL", "lineage_status": "DECLARED",
              "rights": {"status": "SYNTHETIC_FIXTURE", "basis_ref": "rights/basis.txt", "basis_sha256": byte_sha(basis),
                         "collection": True, "retention": True, "derived_index": True, "quotation": True,
                         "reviewed_at": "2026-10-02T00:00:00Z", "takedown_status": "ACTIVE"}}
    row = {"schema_version": "community_knowledge_candidate_v1", "namespace": "neutral_observation",
           "surface_raw": surface, "surface_normalized": surface, "sense_candidate_id": sense or "sense-" + str(index),
           "definition_text": definition, "relation_type": "PRESENTED_EXPLICIT_DEFINITION_STATEMENT", "review_status": "UNREVIEWED",
           "community_scope": [community], "temporal_scope": {"valid_from": "2026-10-01T00:00:00Z", "valid_to": None, "time_unknown_reason": None},
           "source_refs": [{"source_id": sid, "utf8_byte_span_start": 0, "utf8_byte_span_end": len(payload),
                            "evidence_text": statement, "evidence_utf8_sha256": byte_sha(payload)}]}
    row["candidate_id"] = ck.candidate_id_for(row)
    return source, seal(row), {source["payload_ref"]: payload, "rights/basis.txt": basis}


def snapshot(tmp_path, items=None, *, aliases=None, lexicon=None, manifest_change=None, extra_files=None):
    if items is None:
        items = [source_and_candidate()]
    tmp_path.mkdir(parents=True, exist_ok=True)
    sources = [item[0] for item in items]
    candidates = [item[1] for item in items]
    all_files = {}
    for item in items:
        all_files.update(item[2])
    all_files.update(extra_files or {})
    objects = {"candidate_ledger": candidates, "work_alias_registry": aliases or [], "community_lexicon": lexicon or []}
    specs = {}
    for name, rows in objects.items():
        raw = b"".join(encoded(row) + b"\n" for row in rows)
        relative = name + ".jsonl"
        all_files[relative] = raw
        specs[name] = {"path": relative, "sha256": byte_sha(raw), "rows": len(rows)}
    inventory = encoded({"schema_version": "community_knowledge_source_inventory_v1", "sources": sources})
    all_files["source_inventory.json"] = inventory
    specs["source_inventory"] = {"path": "source_inventory.json", "sha256": byte_sha(inventory), "source_count": len(sources)}
    manifest = {"schema_version": ck.MANIFEST_SCHEMA, "snapshot_id": "synthetic-test", "data_kind": "SYNTHETIC_FIXTURE",
                "built_at": "2026-10-10T00:00:00Z", "freeze_cutoff": "2026-10-09T00:00:00Z",
                "parser_version": "raw-captured-utf8-neutral-observation-core-v1", "normalization_version": "utf8_identity_v1",
                "query_policy_version": ck.QUERY_POLICY_VERSION, "rights_policy_version": "local_asserted_reuse_v1",
                "lineage_policy_version": "declared_root_no_independent_authority_v1", "files": specs}
    if manifest_change:
        manifest_change(manifest)
    all_files["manifest.json"] = encoded(manifest)
    for relative, raw in all_files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    path = tmp_path / "manifest.json"
    return path, byte_sha(all_files["manifest.json"])


def view(text="아생갤", *, community="community-a", as_of="2026-10-08T00:00:00Z"):
    return {"schema_version": ck.SOURCE_VIEW_SCHEMA, "post_id": 123,
            "fragments": [{"raw_path": "/title", "kind": "TITLE", "text": text}],
            "community": {"value": community, "source_path": "/gallery_id", "status": "EXPLICIT"},
            "as_of": {"value": as_of, "source_path": "/created_at", "status": "EXPLICIT"}}


def load(tmp_path, *args, **kwargs):
    path, sha = snapshot(tmp_path, *args, **kwargs)
    return ck.load_snapshot(path, expected_sha256=sha)


def assert_digest(receipt):
    copied = deepcopy(receipt)
    wanted = copied.pop("receipt_sha256")
    assert ck.canonical_sha256(copied) == wanted
    assert len(encoded(receipt)) <= ck.MAX_RECEIPT_BYTES


def test_loader_source_binding_and_immutable_queries(tmp_path, monkeypatch):
    store = load(tmp_path)
    original_files = {str(path): byte_sha(path.read_bytes()) for path in tmp_path.rglob("*") if path.is_file()}
    source_view = view("앞 아생갤 뒤")
    before = deepcopy(source_view)
    def no_io(*args, **kwargs):
        raise AssertionError("query must not read files")
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", no_io)
        receipt = store.query(source_view)
        assert receipt["status"] == "OK"
        assert store.summary()["status"] == "AVAILABLE"
    assert receipt["consumption"] == {"status": "QUERY_ONLY"}
    assert receipt["query_sha256"] == ck.canonical_sha256(source_view)
    assert receipt["public_authority"] is receipt["central_db_write"] is receipt["public_apply"] is False
    assert receipt["candidates"][0]["review_status"] == "UNREVIEWED"
    assert receipt["occurrences"][0]["utf8_byte_span_start"] == len("앞 ".encode())
    assert source_view == before
    assert_digest(receipt)
    receipt["candidates"][0]["definition"] = "mutated caller result"
    store.summary()["counts"].clear()
    assert store.query(source_view)["candidates"][0]["definition"] == "합성 작품 약어"
    assert store.summary()["counts"]["candidate_ledger"] == 1
    with pytest.raises(FrozenInstanceError):
        store._bundle_json = b"{}"
    assert original_files == {str(path): byte_sha(path.read_bytes()) for path in tmp_path.rglob("*") if path.is_file()}


def test_competing_work_and_lexicon_senses_remain_separate(tmp_path):
    first, second = source_and_candidate(), source_and_candidate(2, definition="합성 서사 장치")
    review_bytes = b"SYNTHETIC CLASSIFICATION ONLY"
    review = {"authority": "SYNTHETIC_FIXTURE", "reviewer": "fixture", "receipt_ref": "review.txt", "receipt_sha256": byte_sha(review_bytes)}
    alias = seal({"schema_version": "community_knowledge_work_alias_v1", "registry_entry_id": "alias-1", "candidate_id": first[1]["candidate_id"],
                  "review": review, "explicit_alias_assertion_ref": first[1]["source_refs"][0], "work_id": "synthetic-work", "edition_id": None,
                  "media_type": "WEB_NOVEL", "canonical_title": "합성 아카데미 생존 갤러리", "canonical_title_locator": "fixture://work"})
    row = second[1]
    term = seal({"schema_version": "community_knowledge_lexicon_v1", "lexicon_entry_id": "lexicon-1", "candidate_id": row["candidate_id"],
                 "sense_id": row["sense_candidate_id"], "definition": row["definition_text"], "term_kind": "NARRATIVE_DEVICE",
                 "community_scope": row["community_scope"], "temporal_scope": row["temporal_scope"], "competing_sense_ids": ["sense-1"], "review": review})
    receipt = load(tmp_path, [first, second], aliases=[alias], lexicon=[term], extra_files={"review.txt": review_bytes}).query(view())
    assert receipt["status"] == "AMBIGUOUS"
    assert set(receipt["occurrences"][0]["sense_ids"]) == {"sense-1", "sense-2"}
    by_id = {row["sense_id"]: row for row in receipt["candidates"]}
    assert by_id["sense-1"]["work_alias_entries"][0]["work_id"] == "synthetic-work"
    assert by_id["sense-1"]["lexicon_entries"] == []
    assert by_id["sense-2"]["lexicon_entries"][0]["term_kind"] == "NARRATIVE_DEVICE"
    assert by_id["sense-2"]["work_alias_entries"] == []
    assert by_id["sense-1"]["review_status"] == "UNREVIEWED"
    assert_digest(receipt)


@pytest.mark.parametrize("text", ["아생갤러리", "초아생갤", "아생갤은", "_아생갤", "아생갤1", "아생갤\u0301"])
def test_short_surface_not_inside_other_words(tmp_path, text):
    assert load(tmp_path).query(view(text))["status"] == "NO_MATCH"


def test_fragment_boundaries_and_ocr_exclusion(tmp_path):
    store = load(tmp_path)
    query = view("아생")
    query["fragments"].append({"kind": "BODY", "raw_path": "/content", "text": "갤"})
    assert store.query(query)["status"] == "NO_MATCH"
    query["fragments"] = [{"kind": "OCR", "raw_path": "/ocr_text", "text": "아생갤"}]
    assert store.query(query)["status"] == "INVALID_INPUT"
    query["fragments"] = [{"kind": "BODY", "raw_path": "/analysis_result/resolved_title", "text": "아생갤"}]
    assert store.query(query)["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("field", ["community", "as_of"])
def test_unknown_context_is_not_wildcard(tmp_path, field):
    query = view()
    query[field] = {"status": "UNKNOWN", "value": None, "source_path": None}
    receipt = load(tmp_path).query(query)
    assert receipt["status"] == "UNRESOLVED_CONTEXT"
    assert receipt["candidates"] == []
    assert_digest(receipt)


def test_time_and_community_filter_no_future_leak(tmp_path):
    item = source_and_candidate()
    row = item[1]
    row["temporal_scope"]["valid_to"] = "2026-10-08T00:00:00Z"
    seal(row)
    store = load(tmp_path, [item])
    assert store.query(view(as_of="2026-10-07T23:59:59Z"))["status"] == "OK"
    assert store.query(view(as_of="2026-10-08T00:00:00Z"))["excluded_counts"] == {"SENSE_OUTSIDE_VALIDITY": 1}
    assert store.query(view(as_of="2026-10-01T00:00:00Z"))["excluded_counts"] == {"SOURCE_NOT_YET_AVAILABLE": 1}
    assert store.query(view(community="other"))["excluded_counts"] == {"COMMUNITY_MISMATCH": 1}
    receipt = store.query(view(as_of="2026-10-07T00:00:00"))
    assert receipt["status"] == "INVALID_INPUT"
    assert "TIMESTAMP_INVALID" in receipt["reason_codes"]


def test_freeze_cutoff_and_rights_review_time(tmp_path):
    item = source_and_candidate()
    item[0]["available_at"] = "2026-10-09T12:00:00Z"
    store = load(tmp_path / "future", [item])
    assert store.query(view(as_of="2026-10-10T00:00:00Z"))["excluded_counts"] == {"SOURCE_NOT_YET_AVAILABLE": 1}
    item = source_and_candidate()
    item[0]["rights"]["reviewed_at"] = "2026-10-09T00:00:00Z"
    assert load(tmp_path / "rights", [item]).query(view())["excluded_counts"] == {"RIGHTS_NOT_YET_REVIEWED": 1}


@pytest.mark.parametrize("unknown", ["time", "community", "sense_time", "rights", "permission", "lineage"])
def test_unknown_source_fields_are_not_invented(tmp_path, unknown):
    item = source_and_candidate()
    source, row, _ = item
    if unknown == "time":
        source["available_at"], source["time_unknown_reason"] = None, "not recorded"
    elif unknown == "community":
        source["community_scope"] = []
    elif unknown == "sense_time":
        row["temporal_scope"] = {"valid_from": None, "valid_to": None, "time_unknown_reason": "not recorded"}
        seal(row)
    elif unknown == "rights":
        source["rights"]["status"] = "UNKNOWN"
    elif unknown == "permission":
        source["rights"]["quotation"] = None
    else:
        source["lineage_status"], source["lineage_root_id"] = "UNKNOWN", None
    receipt = load(tmp_path, [item]).query(view())
    if unknown == "lineage":
        assert receipt["status"] == "OK"
        assert receipt["candidates"][0]["declared_lineage_roots"] == []
        assert receipt["candidates"][0]["independent_support_count"] is None
    elif unknown in {"rights", "permission"}:
        assert receipt["status"] == "NO_MATCH"
        assert receipt["excluded_counts"] == {"RIGHTS_NOT_ELIGIBLE": 1}
    else:
        assert receipt["status"] == "UNRESOLVED_CONTEXT"
        assert receipt["candidates"] == []


def test_mirror_refs_preserved_without_independent_support(tmp_path):
    first = source_and_candidate()
    second = source_and_candidate(2, sense="sense-1")
    second[0].update(lineage_root_id="root-1", parent_id="capture-1", derivation_kind="MIRROR")
    receipt = load(tmp_path, [first, second]).query(view())
    assert receipt["status"] == "OK"
    assert receipt["counts"]["sense_count"] == 1
    assert len(receipt["candidates"]) == 2
    roots = {root for row in receipt["candidates"] for root in row["declared_lineage_roots"]}
    assert roots == {"root-1"}
    assert {row["source_refs"][0]["source_id"] for row in receipt["candidates"]} == {"capture-1", "capture-2"}


@pytest.mark.parametrize("mutation, code", [
    (lambda item: item[0]["rights"].update(status="REVOKED"), "RIGHTS_REVOKED_OR_TAKEDOWN"),
    (lambda item: item[0]["rights"].update(takedown_status="REMOVED"), "RIGHTS_REVOKED_OR_TAKEDOWN"),
    (lambda item: item[0]["rights"].update(quotation=1), "FIELD_INVALID"),
    (lambda item: item[0].update(available_at="2026-09-01T00:00:00Z"), "TIME_ORDER_INVALID"),
    (lambda item: item[0].update(available_at=None), "TIME_UNKNOWN_REASON_MISSING"),
    (lambda item: item[1].update(candidate_id="candidate:" + "0" * 64), "CANDIDATE_ID_BINDING_MISMATCH"),
    (lambda item: item[1]["source_refs"][0].update(utf8_byte_span_start=1), "SOURCE_SPAN_SHA256_MISMATCH"),
    (lambda item: item[1].update(definition_text="invented definition"), "NEUTRAL_OBSERVATION_BINDING_MISMATCH"),
    (lambda item: item[1].update(review_status="REVIEWED"), "REVIEW_RECEIPT_MISSING"),
    (lambda item: item[0].update(parent_id="capture-1"), "LINEAGE_INVALID"),
])
def test_invalid_snapshot_fails_closed(tmp_path, mutation, code):
    item = source_and_candidate()
    mutation(item)
    with pytest.raises(ck.CommunityKnowledgeError) as error:
        load(tmp_path, [item])
    assert error.value.code == code


def test_manifest_file_payload_and_basis_hashes(tmp_path):
    path, sha = snapshot(tmp_path)
    with pytest.raises(ck.CommunityKnowledgeError, match="SNAPSHOT_SHA256_MISMATCH"):
        ck.load_snapshot(path, "0" * 64)
    for relative in ("candidate_ledger.jsonl", "payloads/capture-1.txt", "rights/basis.txt"):
        target = tmp_path / relative
        original = target.read_bytes()
        target.write_bytes(original + b"tampered")
        with pytest.raises(ck.CommunityKnowledgeError) as error:
            ck.load_snapshot(path, sha)
        assert error.value.code == "FILE_SHA256_MISMATCH"
        target.write_bytes(original)


@pytest.mark.parametrize("relative", ["../outside.jsonl", "C:/outside.jsonl", "https://example.test/x", "payloads\\x"])
def test_no_path_escape_or_external_fetch(tmp_path, relative):
    path, sha = snapshot(tmp_path, manifest_change=lambda m: m["files"]["candidate_ledger"].update(path=relative))
    with pytest.raises(ck.CommunityKnowledgeError) as error:
        ck.load_snapshot(path, sha)
    assert error.value.code == "PATH_OUTSIDE_SNAPSHOT"


def test_duplicate_ids_and_conflicting_senses(tmp_path):
    first, second = source_and_candidate(), source_and_candidate(2, sense="sense-1", definition="different synthetic sense")
    with pytest.raises(ck.CommunityKnowledgeError) as error:
        load(tmp_path / "duplicate", [first, first])
    assert error.value.code == "DUPLICATE_ID"
    with pytest.raises(ck.CommunityKnowledgeError) as error:
        load(tmp_path / "sense", [first, second])
    assert error.value.code == "SENSE_ID_CONFLICT"


def test_limits_fail_without_partial_candidates(tmp_path):
    store = load(tmp_path)
    for query, reason in ((view("아생갤 " * 33), "OCCURRENCE_LIMIT"), (view("a" * 12001), "QUERY_CHARACTER_LIMIT")):
        receipt = store.query(query)
        assert receipt["status"] == "LIMIT_EXCEEDED"
        assert receipt["reason_codes"] == [reason]
        assert receipt["candidates"] == []
        assert_digest(receipt)
    many = load(tmp_path / "many", [source_and_candidate(n, definition="합성 정의 " + str(n)) for n in range(1, 18)])
    assert many.query(view())["reason_codes"] == ["SENSE_LIMIT"]


def test_unavailable_snapshot_keeps_binding_and_digest():
    store = ck.unavailable_snapshot("FILE_SHA256_MISMATCH", expected_sha256="a" * 64)
    assert store.summary()["status"] == "UNAVAILABLE"
    receipt = store.query(view())
    assert receipt["status"] == "UNAVAILABLE"
    assert receipt["snapshot_sha256"] == "a" * 64
    assert receipt["query_sha256"] == ck.canonical_sha256(view())
    assert receipt["candidates"] == []
    assert_digest(receipt)


def test_concurrent_queries_do_not_cross_contaminate(tmp_path):
    store = load(tmp_path)
    queries = [view("아생갤" if n % 2 else "다른 원문") for n in range(12)]
    for n, query in enumerate(queries):
        query["post_id"] = n
    expected = [store.query(query) for query in queries]
    with ThreadPoolExecutor(max_workers=2) as executor:
        actual = list(executor.map(store.query, queries))
    assert actual == expected
    assert all(item["post_id"] == n for n, item in enumerate(actual))


def test_duplicate_json_keys_and_row_count_rejected(tmp_path):
    path, _ = snapshot(tmp_path / "json")
    raw = path.read_bytes().replace(b'"snapshot_id":', b'"snapshot_id":"duplicate","snapshot_id":')
    path.write_bytes(raw)
    with pytest.raises(ck.CommunityKnowledgeError) as error:
        ck.load_snapshot(path, byte_sha(raw))
    assert error.value.code == "DUPLICATE_JSON_KEY"
    with pytest.raises(ck.CommunityKnowledgeError) as error:
        load(tmp_path / "count", manifest_change=lambda m: m["files"]["candidate_ledger"].update(rows=9))
    assert error.value.code == "ROW_COUNT_MISMATCH"


def test_source_backed_cannot_relabel_synthetic_rights(tmp_path):
    with pytest.raises(ck.CommunityKnowledgeError) as error:
        load(tmp_path, manifest_change=lambda m: m.update(data_kind="SOURCE_BACKED"))
    assert error.value.code == "SYNTHETIC_SOURCE_MIXED"


def test_receipt_size_limit_counts_omissions_and_keeps_hash(tmp_path):
    store = load(tmp_path, [source_and_candidate(n, definition="합성" * 900 + str(n)) for n in range(1, 9)])
    receipt = store.query(view())
    assert receipt["status"] == "LIMIT_EXCEEDED"
    assert receipt["reason_codes"] == ["RECEIPT_BYTE_LIMIT"]
    assert receipt["counts"]["eligible_candidates"] == 8
    assert receipt["counts"]["returned_candidates"] == 0
    assert receipt["candidates"] == receipt["occurrences"] == []
    assert_digest(receipt)


@pytest.mark.parametrize("post_id", [True, [], "\ud800", 2 ** 100])
def test_invalid_post_identity_still_returns_bounded_error_receipt(tmp_path, post_id):
    query = view()
    query["post_id"] = post_id
    receipt = load(tmp_path).query(query)
    assert receipt["status"] == "INVALID_INPUT"
    assert_digest(receipt)


def test_unknown_competitor_keeps_unresolved_status(tmp_path):
    first, second = source_and_candidate(), source_and_candidate(2, definition="다른 합성 의미")
    second[0]["available_at"] = None
    second[0]["time_unknown_reason"] = "not recorded"
    receipt = load(tmp_path, [first, second]).query(view())
    assert receipt["status"] == "UNRESOLVED_CONTEXT"
    assert len(receipt["candidates"]) == 1
    assert receipt["excluded_counts"] == {"SOURCE_TIME_UNKNOWN": 1}


def test_alias_assertion_from_future_ref_is_not_exposed(tmp_path):
    first, second = source_and_candidate(), source_and_candidate(2, sense="sense-1")
    first[1]["source_refs"].extend(second[1]["source_refs"])
    first[1]["candidate_id"] = ck.candidate_id_for(first[1])
    seal(first[1])
    second[0]["available_at"] = "2026-10-09T00:00:00Z"
    review_bytes = b"synthetic classification"
    review = {"authority": "SYNTHETIC_FIXTURE", "reviewer": "fixture", "receipt_ref": "review.txt", "receipt_sha256": byte_sha(review_bytes)}
    alias = seal({"schema_version": "community_knowledge_work_alias_v1", "registry_entry_id": "alias-1", "candidate_id": first[1]["candidate_id"],
                  "review": review, "explicit_alias_assertion_ref": second[1]["source_refs"][0], "work_id": "synthetic-work", "edition_id": None,
                  "media_type": "WEB_NOVEL", "canonical_title": "합성 작품", "canonical_title_locator": "fixture://work"})
    receipt = load(tmp_path, [first, second], aliases=[alias], extra_files={"review.txt": review_bytes}).query(view())
    assert receipt["status"] == "OK"
    assert len(receipt["candidates"]) == 1
    assert receipt["candidates"][0]["work_alias_entries"] == []
    assert receipt["candidates"][0]["source_refs"][0]["source_id"] == "capture-1"
