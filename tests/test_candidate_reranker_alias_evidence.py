"""R3 builder 원문부터 고정 R2 후보까지의 합성 별칭 검산. 실제 품질 시험 아님."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import socket

import pytest

from llm_batch.grounding import candidate_reranker_alias_evidence as ae
from llm_batch.grounding import candidate_retrieval_shadow as retrieval
from llm_batch.grounding import community_knowledge as ck
from llm_batch.grounding import community_knowledge_builder as builder
from llm_batch.grounding import p0_source_profile_raw_parser_core as parser
from llm_batch.grounding.candidate_reranker_shadow import build_frozen_view


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write(path, value):
    raw = encoded(value) + b"\n"
    path.write_bytes(raw)
    return sha(raw)


def build_alias_fixture(tmp_path):
    """공용 합성 helper. 실제 R3 builder/loader와 R2 loader/observe를 사용한다."""
    root = tmp_path / "alias-fixture"
    captures = root / "captures"
    captures.mkdir(parents=True, exist_ok=False)
    payload = "'아생갤'은 아카데미 생존 갤러리를 뜻한다.\n".encode("utf-8")
    basis = "합성 시험용으로 작성한 원문과 검토 기록. 실제 관계와 권리의 증거가 아님.".encode("utf-8")
    (captures / "capture.txt").write_bytes(payload)
    (captures / "rights.txt").write_bytes(basis)
    source = {"source_id": "synthetic-alias-source", "source_ref": "fixture://alias/source", "payload_ref": "capture.txt",
        "payload_byte_sha256": sha(payload), "capture_profile": parser.SUPPORTED_PROFILE,
        "capture_version": parser.SUPPORTED_CAPTURE_VERSION, "normalization_version": parser.SUPPORTED_NORMALIZATION_VERSION,
        "source_published_at": "2026-10-01T00:00:00Z", "source_modified_at": None,
        "captured_at": "2026-10-02T00:00:00Z", "available_at": "2026-10-02T00:00:00Z", "time_unknown_reason": None,
        "community_scope": ["synthetic-novel-community"], "lineage_root_id": "synthetic-lineage", "parent_id": None,
        "derivation_kind": "ORIGINAL", "lineage_status": "DECLARED",
        "rights": {"status": "SYNTHETIC_FIXTURE", "basis_ref": "rights.txt", "basis_sha256": sha(basis),
            "collection": True, "retention": True, "derived_index": True, "quotation": True,
            "reviewed_at": "2026-10-02T00:00:00Z", "takedown_status": "ACTIVE"}}
    observation = parser.parse_capture(source_profile=source["capture_profile"], content_type=parser.SUPPORTED_CONTENT_TYPE,
        capture_version=source["capture_version"], normalization_version=source["normalization_version"], payload=payload)["observations"][0]
    classification = {"namespace": "work_alias_registry", "work_id": "synthetic-work-1", "edition_id": "synthetic-edition-1",
        "media_type": "WEB_NOVEL", "canonical_title": "아카데미 생존 갤러리", "canonical_title_locator": "fixture://alias/work-1"}
    review = {"schema_version": builder.REVIEW_SCHEMA, "source_id": source["source_id"], "payload_byte_sha256": sha(payload),
        "observation_sha256": observation["observation_sha256"], "review_status": "REVIEWED", "authority": "SYNTHETIC_FIXTURE",
        "reviewer": "synthetic-fixture-author", "sense_candidate_id": "synthetic-work-sense", "classification": classification}
    review_sha = _write(captures / "review.json", review)
    capture = {"source": source, "content_type": parser.SUPPORTED_CONTENT_TYPE,
        "temporal_scope": {"valid_from": "2026-10-01T00:00:00Z", "valid_to": None, "time_unknown_reason": None},
        "reviews": [{"path": "review.json", "sha256": review_sha}]}
    spec = {"schema_version": builder.CAPTURE_SCHEMA, "snapshot_id": "synthetic-alias-snapshot", "data_kind": "SYNTHETIC_FIXTURE",
        "built_at": "2026-10-05T00:00:00Z", "freeze_cutoff": "2026-10-04T00:00:00Z", "captures": [capture]}
    spec_path = captures / "captures.json"
    _write(spec_path, spec)
    output = root / "snapshot"
    build_receipt = builder.build_snapshot(spec_path, output, capture_root=captures, output_root=root)
    original_store = ck.load_snapshot(output / "manifest.json", expected_sha256=build_receipt["snapshot_sha256"])
    assert original_store.summary()["data_kind"] == "SYNTHETIC_FIXTURE"
    manifest = json.loads((output / "manifest.json").read_bytes())
    snapshot_files = {path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob("*")
                      if path.is_file() and path != output / "manifest.json"}
    entries = []
    for i, title in enumerate(("아카데미 생존 갤러리", "합성 별빛 도서관"), 1):
        aliases, text = [], "아생갤 합성후보"
        entries.append({"corpus_candidate_id": f"synthetic-corpus-{i}", "work_id": f"synthetic-work-{i}", "edition_id": f"synthetic-edition-{i}",
            "media_type": "WEB_NOVEL", "title": title, "aliases": aliases, "text": text,
            "content_sha256": retrieval.candidate_content_sha256(title, aliases, text),
            "sources": [{"source_ref": f"fixture://corpus/{i}", "source_sha256": sha(f"synthetic-{i}".encode()),
                "lineage_id": f"synthetic-corpus-root-{i}", "observed_at": "2026-10-03T00:00:00Z",
                "rights": {"status": "SYNTHETIC_FIXTURE", "basis": "repository synthetic test only"}}]})
    corpus = {"schema_version": retrieval.CORPUS_SCHEMA, "corpus_id": "synthetic-alias-corpus", "data_kind": "SYNTHETIC_FIXTURE", "entries": entries}
    corpus_path = root / "corpus.json"
    corpus_path.write_bytes(encoded(corpus))
    corpus_sha = sha(corpus_path.read_bytes())
    r2_source = {"schema_version": retrieval.SOURCE_VIEW_SCHEMA, "post_id": 12001,
                 "fragments": [{"raw_path": "/title", "kind": "TITLE", "text": "아생갤"},
                               {"raw_path": "/content", "kind": "BODY", "text": "합성후보"}]}
    r2 = retrieval.load_corpus(corpus_path, expected_sha256=corpus_sha).observe(r2_source)
    view = build_frozen_view(r2_source, r2)
    query = ae.build_alias_community_source_view(r2_source,
        community={"value": "synthetic-novel-community", "status": "EXPLICIT", "source_path": "/gallery_id"},
        as_of={"value": "2026-10-08T00:00:00Z", "status": "EXPLICIT", "source_path": "/created_at"})
    fixture = {"manifest": manifest, "snapshot_files": snapshot_files, "corpus": corpus,
        "frozen_view": view, "retrieval_receipt": r2, "community_source_view": query,
        "alias_evidence": {}, "evidence_payloads": {}, "call_evidence": {}}
    _refresh(fixture)
    return fixture


def _refresh(fixture):
    """변조 반례의 바깥 해시만 갱신한다. 의미·review·source 결속은 자동 수리하지 않는다."""
    files, manifest = fixture["snapshot_files"], fixture["manifest"]
    for name, spec in manifest["files"].items():
        raw = files[spec["path"]]
        spec["sha256"] = sha(raw)
        spec["source_count" if name == "source_inventory" else "rows"] = len(json.loads(raw)["sources"]) if name == "source_inventory" else len(raw.splitlines())
    raw_manifest, corpus_raw = encoded(manifest), encoded(fixture["corpus"])
    fixture["alias_evidence"] = {"schema_version": ae.INPUT_SCHEMA, "snapshot_manifest_sha256": sha(raw_manifest),
        "snapshot_files": {name: sha(raw) for name, raw in files.items()}, "corpus_sha256": sha(corpus_raw)}
    fixture["evidence_payloads"] = {sha(raw): raw for raw in [raw_manifest, corpus_raw, *files.values()]}
    fixture["call_evidence"] = {**fixture["alias_evidence"], "retrieval_receipt": fixture["retrieval_receipt"],
                                "community_source_view": fixture["community_source_view"]}


def _rows(fixture, name):
    return [json.loads(line) for line in fixture["snapshot_files"][fixture["manifest"]["files"][name]["path"]].splitlines()]


def _set_rows(fixture, name, rows):
    for row in rows:
        row["row_content_sha256"] = ck.row_content_sha256(row)
    fixture["snapshot_files"][fixture["manifest"]["files"][name]["path"]] = b"".join(encoded(row) + b"\n" for row in rows)


def _inventory(fixture):
    return json.loads(fixture["snapshot_files"][fixture["manifest"]["files"]["source_inventory"]["path"]])


def _set_inventory(fixture, value):
    fixture["snapshot_files"][fixture["manifest"]["files"]["source_inventory"]["path"]] = encoded(value)


def _rebind_review(fixture, change):
    ledger, aliases = _rows(fixture, "candidate_ledger"), _rows(fixture, "work_alias_registry")
    reference = aliases[0]["review"]
    review = json.loads(fixture["snapshot_files"][reference["receipt_ref"]])
    change(review, ledger[0], aliases[0])
    raw = encoded(review)
    fixture["snapshot_files"][reference["receipt_ref"]] = raw
    for row in (ledger[0], aliases[0]):
        row["review"]["receipt_sha256"] = sha(raw)
    _set_rows(fixture, "candidate_ledger", ledger)
    _set_rows(fixture, "work_alias_registry", aliases)
    _refresh(fixture)


def _rescore_fixture(fixture, tmp_path, text=None):
    if text is not None:
        fixture["frozen_view"]["source_view"]["fragments"][0]["text"] = text
    source = fixture["frozen_view"]["source_view"]
    path = tmp_path / "modified-corpus.json"
    path.write_bytes(encoded(fixture["corpus"]))
    r2 = retrieval.load_corpus(path, expected_sha256=sha(path.read_bytes())).observe(source)
    fixture["retrieval_receipt"] = r2
    fixture["frozen_view"] = build_frozen_view(source, r2)
    fixture["community_source_view"]["fragments"] = deepcopy(source["fragments"])
    _refresh(fixture)


def _observe(fixture):
    return ae.observe_alias_evidence(fixture["frozen_view"], alias_evidence=fixture["call_evidence"], evidence_payloads=fixture["evidence_payloads"])


@pytest.fixture
def fixture(tmp_path):
    return build_alias_fixture(tmp_path)


def test_builder_loader_real_r2_binding_is_pure_immutable_and_deterministic(fixture, monkeypatch):
    before = deepcopy(fixture)
    prepared = ae.prepare_alias_evidence(alias_evidence=fixture["alias_evidence"], evidence_payloads=fixture["evidence_payloads"])
    def forbidden(*args, **kwargs):
        raise AssertionError("순수 validator는 IO 금지")
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        result = _observe(fixture)
        again = prepared.observe(fixture["frozen_view"], retrieval_receipt=fixture["retrieval_receipt"], community_source_view=fixture["community_source_view"])
    assert result == again
    assert result["status"] == "BOUND" and len(result["bindings"]) == 1
    binding = result["bindings"][0]
    assert binding["candidate_id"] == "synthetic-corpus-1" and binding["alias"] == "아생갤"
    assert binding["evidence_grade"] == "SYNTHETIC_FIXTURE_BOUND"
    assert all(result[key] is False for key in ("publication_authority", "public_apply", "central_db_write", "actual_semantic_evidence_verified", "reviewer_identity_verified"))
    assert fixture == before
    digest = result.pop("receipt_sha256")
    assert ae.canonical_sha256(result) == digest
    assert len(encoded(result)) <= ae.MAX_RECEIPT_BYTES
    with pytest.raises(FrozenInstanceError):
        prepared._bundle_json = b"{}"
    prepared.summary()["status"] = "changed"
    assert prepared.summary()["status"] == "AVAILABLE"


def test_relation_and_runtime_occurrence_are_exact_utf8_slices(fixture):
    result = _observe(fixture)
    assert result["status"] == "BOUND"
    binding = result["bindings"][0]
    payload = fixture["evidence_payloads"][binding["payload_sha256"]]
    for key, expected in (("alias_utf8_span", "아생갤"), ("title_utf8_span", "아카데미 생존 갤러리"), ("predicate_utf8_span", "뜻한다")):
        start, end = binding["relation"][key]
        assert payload[start:end].decode("utf-8") == expected
    start, end = binding["relation"]["raw_utf8_span"]
    assert sha(payload[start:end]) == binding["relation"]["text_sha256"]
    assert binding["occurrences"][0]["text_sha256"] == sha("아생갤".encode())


@pytest.mark.parametrize("authority", ["MODEL_REFERENCE", "UNKNOWN", "HUMAN_REVIEW"])
def test_synthetic_review_never_becomes_human_evidence(fixture, authority):
    def change(review, row, alias):
        review["authority"] = row["review"]["authority"] = alias["review"]["authority"] = authority
    _rebind_review(fixture, change)
    result = _observe(fixture)
    assert result["bindings"] == [] and "REVIEW_AUTHORITY_INSUFFICIENT" in result["reason_codes"]


@pytest.mark.parametrize("field", ["source_id", "payload_byte_sha256", "observation_sha256", "sense_candidate_id", "reviewer"])
def test_review_original_json_binding_cannot_be_replaced_by_a_fresh_outer_hash(fixture, field):
    _rebind_review(fixture, lambda review, row, alias: review.update({field: "0" * 64 if field.endswith("sha256") else "foreign"}))
    result = _observe(fixture)
    assert result["bindings"] == [] and "REVIEW_SOURCE_CLASSIFICATION_BINDING_MISMATCH" in result["reason_codes"]


def test_review_classification_title_not_in_relation_fails(fixture):
    def change(review, row, alias):
        review["classification"]["canonical_title"] = alias["canonical_title"] = "다른 제목"
    _rebind_review(fixture, change)
    assert "CANONICAL_TITLE_MISMATCH" in _observe(fixture)["reason_codes"]


@pytest.mark.parametrize("field", ["work_id", "edition_id", "media_type"])
def test_same_title_does_not_guess_work_edition_media_ids(fixture, field):
    def change(review, row, alias):
        value = "WEBTOON" if field == "media_type" else "foreign-id"
        review["classification"][field] = alias[field] = value
    _rebind_review(fixture, change)
    assert "ID_MAPPING_MISSING" in _observe(fixture)["reason_codes"]


def test_unknown_edition_is_not_wildcard(fixture):
    def change(review, row, alias):
        review["classification"]["edition_id"] = alias["edition_id"] = None
    _rebind_review(fixture, change)
    assert "EDITION_UNKNOWN" in _observe(fixture)["reason_codes"]


def test_duplicate_fixed_identity_is_ambiguous_but_exact_mirror_collapses(fixture, tmp_path):
    duplicate = deepcopy(fixture["corpus"]["entries"][0])
    duplicate["corpus_candidate_id"] = "synthetic-corpus-1-mirror"
    fixture["corpus"]["entries"].append(duplicate)
    _rescore_fixture(fixture, tmp_path)
    assert _observe(fixture)["status"] == "BOUND"
    duplicate["text"] += " 다른내용"
    duplicate["content_sha256"] = retrieval.candidate_content_sha256(duplicate["title"], duplicate["aliases"], duplicate["text"])
    _rescore_fixture(fixture, tmp_path)
    assert "ID_MAPPING_AMBIGUOUS" in _observe(fixture)["reason_codes"]


def test_same_title_distinct_works_remain_distinct(fixture, tmp_path):
    second = fixture["corpus"]["entries"][1]
    second["title"] = fixture["corpus"]["entries"][0]["title"]
    second["content_sha256"] = retrieval.candidate_content_sha256(second["title"], second["aliases"], second["text"])
    _rescore_fixture(fixture, tmp_path)
    result = _observe(fixture)
    assert result["status"] == "BOUND" and result["bindings"][0]["candidate_id"] == "synthetic-corpus-1"


@pytest.mark.parametrize("text,expected", [("아생갤은 좋다", "BOUND"), ("아생갤\n후기", "BOUND"), ("아생갤\t후기", "BOUND"),
    ("아생갤러리", "NO_MATCH"), ("초아생갤", "NO_MATCH"), ("아생갤은행", "NO_MATCH"), ("아생갤\u200b", "NO_MATCH")])
def test_literal_alias_boundaries_and_gallery_name_noninference(fixture, tmp_path, text, expected):
    _rescore_fixture(fixture, tmp_path, text)
    assert _observe(fixture)["status"] == expected


@pytest.mark.parametrize("key", ["community", "as_of"])
def test_unknown_context_is_not_guessed(fixture, key):
    fixture["community_source_view"][key].update(value=None, status="UNKNOWN")
    assert _observe(fixture)["reason_codes"] == ["CONTEXT_UNKNOWN"]


def test_unknown_value_and_nonoriginal_context_path_are_rejected(fixture):
    fixture["community_source_view"]["community"]["status"] = "UNKNOWN"
    assert _observe(fixture)["reason_codes"] == ["UNKNOWN_CONTEXT_VALUE_NOT_NULL"]
    fixture["community_source_view"]["community"]["status"] = "EXPLICIT"
    fixture["community_source_view"]["as_of"]["source_path"] = "/analysis_result/time"
    assert _observe(fixture)["reason_codes"] == ["CONTEXT_SOURCE_PATH_INVALID"]


def test_corpus_future_observation_remains_unresolved(fixture, tmp_path):
    source = fixture["corpus"]["entries"][0]["sources"][0]
    source["observed_at"] = "2026-10-09T00:00:00Z"
    _rescore_fixture(fixture, tmp_path)
    assert _observe(fixture)["reason_codes"] == ["CORPUS_SOURCE_NOT_YET_OBSERVED"]


def test_different_community_and_future_snapshot_never_bind(fixture):
    fixture["community_source_view"]["community"]["value"] = "other-community"
    assert "COMMUNITY_MISMATCH" in _observe(fixture)["reason_codes"]
    fixture["community_source_view"]["community"]["value"] = "synthetic-novel-community"
    fixture["community_source_view"]["as_of"]["value"] = "2026-10-04T00:00:00Z"
    assert _observe(fixture)["reason_codes"] == ["SNAPSHOT_AFTER_AS_OF"]


@pytest.mark.parametrize("mode,reason", [("rights", "RIGHTS_NOT_ELIGIBLE"), ("lineage", "LINEAGE_UNKNOWN"),
    ("time", "SOURCE_TIME_UNKNOWN"), ("rights_future", "RIGHTS_NOT_YET_REVIEWED")])
def test_rights_time_lineage_unknowns_remain_unbound(fixture, mode, reason):
    inventory = _inventory(fixture)
    source = inventory["sources"][0]
    if mode == "rights":
        source["rights"]["quotation"] = None
    elif mode == "lineage":
        source["lineage_status"], source["lineage_root_id"] = "UNKNOWN", None
    elif mode == "time":
        source["available_at"], source["time_unknown_reason"] = None, "시험 미상"
    else:
        source["rights"]["reviewed_at"] = "2026-10-05T00:00:00Z"
    _set_inventory(fixture, inventory)
    _refresh(fixture)
    assert reason in _observe(fixture)["reason_codes"]


def test_source_span_raw_hash_and_parser_replay_are_required(fixture):
    ledger, aliases = _rows(fixture, "candidate_ledger"), _rows(fixture, "work_alias_registry")
    ledger[0]["source_refs"][0]["utf8_byte_span_end"] -= 1
    ledger[0]["candidate_id"] = ck.candidate_id_for(ledger[0])
    aliases[0]["candidate_id"] = ledger[0]["candidate_id"]
    aliases[0]["explicit_alias_assertion_ref"] = deepcopy(ledger[0]["source_refs"][0])
    _set_rows(fixture, "candidate_ledger", ledger)
    _set_rows(fixture, "work_alias_registry", aliases)
    _refresh(fixture)
    result = _observe(fixture)
    assert result["status"] == "INVALID_INPUT" and "SOURCE_SPAN_SHA256_MISMATCH" in result["reason_codes"]


@pytest.mark.parametrize("mutation", ["payload", "missing", "map", "absolute_path", "traversal", "extra_key", "bool_post", "changed_source", "id_order"])
def test_input_bindings_and_pins_fail_closed(fixture, mutation):
    if mutation == "payload":
        key = next(iter(fixture["evidence_payloads"]))
        fixture["evidence_payloads"][key] += b"changed"
    elif mutation == "missing":
        fixture["evidence_payloads"].pop(fixture["alias_evidence"]["corpus_sha256"])
    elif mutation == "map":
        # 보조 build_receipt가 아니라 manifest가 반드시 소비하는 파일 핀을 바꾼다.
        key = fixture["manifest"]["files"]["candidate_ledger"]["path"]
        fixture["call_evidence"]["snapshot_files"][key] = fixture["call_evidence"]["corpus_sha256"]
    elif mutation in {"absolute_path", "traversal"}:
        fixture["call_evidence"]["snapshot_files"]["/absolute" if mutation == "absolute_path" else "../outside"] = fixture["call_evidence"]["corpus_sha256"]
    elif mutation == "extra_key":
        fixture["call_evidence"]["human_verified"] = True
    elif mutation == "bool_post":
        fixture["frozen_view"]["post_id"] = True
    elif mutation == "changed_source":
        fixture["community_source_view"]["fragments"][0]["text"] += " altered"
    else:
        fixture["frozen_view"]["candidates"].reverse()
    result = _observe(fixture)
    assert result["status"] == "INVALID_INPUT" and not result["bindings"]
    if mutation == "map":
        assert result["reason_codes"] == ["SNAPSHOT_FILE_BINDING_MISMATCH"]


def test_resigned_r2_work_identity_must_match_pinned_corpus(fixture):
    r2 = fixture["retrieval_receipt"]
    r2["ranked_candidates"][0]["work_id"] = "foreign-work"
    r2["observation_sha256"] = retrieval._sha({key: value for key, value in r2.items() if key not in {"observation_sha256", "latency_ms", "binding"}})
    fixture["frozen_view"] = build_frozen_view(fixture["frozen_view"]["source_view"], r2)
    result = _observe(fixture)
    assert result["reason_codes"] == ["RETRIEVAL_CORPUS_IDENTITY_MISMATCH"] and not result["bindings"]


def test_truncated_candidates_and_invalid_policy_do_not_bind(fixture):
    r2 = fixture["retrieval_receipt"]
    r2["counts"]["positive_candidates"] += 1
    r2["observation_sha256"] = retrieval._sha({key: value for key, value in r2.items() if key not in {"observation_sha256", "latency_ms", "binding"}})
    fixture["frozen_view"] = build_frozen_view(fixture["frozen_view"]["source_view"], r2)
    assert _observe(fixture)["reason_codes"] == ["GENERATION_NOT_COMPLETE"]
    r2["policy"] = []
    r2["observation_sha256"] = retrieval._sha({key: value for key, value in r2.items() if key not in {"observation_sha256", "latency_ms", "binding"}})
    fixture["frozen_view"] = build_frozen_view(fixture["frozen_view"]["source_view"], r2)
    assert _observe(fixture)["reason_codes"] == ["RETRIEVAL_POLICY_INVALID"]


def test_occurrence_and_receipt_limits_do_not_publish_partial_success(fixture, tmp_path, monkeypatch):
    _rescore_fixture(fixture, tmp_path, " ".join(["아생갤"] * 129))
    result = _observe(fixture)
    assert result["status"] == "LIMIT_EXCEEDED" and result["bindings"] == []
    _rescore_fixture(fixture, tmp_path, "아생갤")
    monkeypatch.setattr(ae, "MAX_RECEIPT_BYTES", 1800)
    result = _observe(fixture)
    assert result["status"] == "LIMIT_EXCEEDED" and result["bindings"] == []


def test_input_byte_limit_checked_before_snapshot_decode(fixture, monkeypatch):
    monkeypatch.setattr(ae, "MAX_INPUT_BYTES", 100)
    result = _observe(fixture)
    assert result["status"] == "LIMIT_EXCEEDED" and result["bindings"] == []
    assert result["reason_codes"] == ["ALIAS_INPUT_BYTE_LIMIT"]


def test_competing_neutral_sense_blocks_alias_without_turning_gallery_into_place(fixture):
    rows = _rows(fixture, "candidate_ledger")
    other = deepcopy(rows[0])
    other["sense_candidate_id"] = "another-sense"
    other["candidate_id"] = ck.candidate_id_for(other)
    # 미검토 관측 역시 경쟁 의미의 존재로 남긴다. 작품/현실 장소 판정은 하지 않는다.
    other["review_status"] = "UNREVIEWED"
    other.pop("review")
    rows.append(other)
    _set_rows(fixture, "candidate_ledger", rows)
    _refresh(fixture)
    result = _observe(fixture)
    assert result["status"] == "AMBIGUOUS" and result["bindings"] == []
    assert "COMPETING_SENSES" in result["reason_codes"]


def test_explicit_source_backed_schema_needs_full_review_and_source_bytes(fixture, tmp_path):
    # 이 입력은 SOURCE_BACKED 계약의 합성 반례/양성 모양이다. 실제 자료 검증 증거 아님.
    fixture["manifest"]["data_kind"] = fixture["corpus"]["data_kind"] = "SOURCE_BACKED"
    inventory = _inventory(fixture)
    inventory["sources"][0]["rights"]["status"] = "REUSE_PERMITTED"
    _set_inventory(fixture, inventory)
    for entry in fixture["corpus"]["entries"]:
        for source in entry["sources"]:
            source["rights"]["status"] = "REUSE_PERMITTED"
    def change(review, row, alias):
        review["authority"] = row["review"]["authority"] = alias["review"]["authority"] = "HUMAN_REVIEW"
    _rebind_review(fixture, change)
    _rescore_fixture(fixture, tmp_path)
    result = _observe(fixture)
    assert result["status"] == "BOUND" and result["bindings"][0]["evidence_grade"] == "HUMAN_REVIEW_BOUND"
    assert result["actual_semantic_evidence_verified"] is False
    assert result["reviewer_identity_verified"] is False
    # authority 하나만 바꾸거나 원문 review를 생략하면 binding을 얻지 못한다.
    digest = result["bindings"][0]["review_receipt_sha256"]
    fixture["evidence_payloads"].pop(digest)
    assert _observe(fixture)["bindings"] == []
