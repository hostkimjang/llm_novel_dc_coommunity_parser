"""실제 provider 계획의 원본 결속·보존 경계. 전송·모델 호출 없이 검산한다."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path

import pytest

from src.llm_batch.measurement import recovery_provider_contract as contract
from src.llm_batch.measurement import recovery_execution_contract as simulation
from src.llm_batch.runtime.recovery_transport import _endpoint, _payload
from src.llm_batch.ledger.recovery_provider_journal import configuration
from src.llm_batch.ledger.publication_commit import PublicationCommitError
from tests.recovery_provider_fixtures import build_recovery_provider_fixture
from tests.recovery_execution_fixtures import json_bytes


@pytest.fixture
def bundle(tmp_path):
    return build_recovery_provider_fixture(tmp_path)


def replace_raw(kwargs, role, raw):
    kwargs["source_bytes"][role] = raw
    kwargs["source_refs"][role]["sha256"] = hashlib.sha256(raw).hexdigest()
    kwargs["source_refs"][role]["bytes"] = len(raw)


def replace_json(kwargs, role, value, *, lines=False):
    replace_raw(kwargs, role, json_bytes(value) + (b"\n" if lines else b""))


def test_valid_plan_binds_real_manifest_fields_without_claiming_real_data_or_guard(bundle):
    plan, bound = bundle["plan"], bundle["bound"]
    assert plan["data_kind"] == "TEST_SYNTHETIC"
    assert plan["execution_mode"] == "EXPLICIT_PROVIDER_EVIDENCE_ONLY"
    assert plan["guard_status"] == "GUARD_NOT_EVALUATED"
    assert plan["base"]["export_run_id"] == "provider-export-fixture"
    assert plan["base"]["base_attempt_run_id"] == "original-owner-fixture"
    assert all(plan[key] is False for key in ("public_apply", "publication_authority", "central_db_write", "actual_quality_evaluated"))
    assert bound.verify_protected_sources() is True
    assert len(bound.input_rows) == 2 and len(bound.input_bindings["records"]) == 3
    assert bound.input_bindings["post_bindings"][0]["result_comments"] == ["합성 독자 원문 댓글"]
    assert not bound.output_dir.exists()
    with pytest.raises(ValueError):
        simulation.validate_plan(plan)


def test_provider_journal_and_wire_contract_use_identical_body_endpoint_policy(bundle):
    plan, bound = bundle["plan"], bundle["bound"]
    args = contract.provider_journal_arguments(plan)
    checked = configuration(**args)
    assert checked == (args["binding"], args["policy"], args["requests"])
    assert bound.binding == args["binding"] and bound.requests == args["requests"]
    request = plan["request"]
    assert request["kind"] == "MCP_SEARCH" and request["request_id"] == "targeted-search-1"
    assert request["body_sha256"] == hashlib.sha256(_payload("MCP_SEARCH", bound.payload)).hexdigest()
    assert request["endpoint_sha256"] == hashlib.sha256(_endpoint(request["endpoint"]).encode()).hexdigest()
    assert args["binding"]["policy_sha256"] == contract._sha(bound.policy)
    assert plan["artifacts"] == plan["source_refs"]


def test_build_is_pure_and_bound_accessors_do_not_expose_mutable_state(bundle, monkeypatch):
    before = {role: Path(ref["path"]).read_bytes() for role, ref in bundle["source_refs"].items()}
    def forbidden(*args, **kwargs):
        raise AssertionError("순수 builder가 파일을 열었음")
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(os, "open", forbidden)
        assert contract.build_recovery_provider_plan(**bundle["build_kwargs"]) == bundle["plan"]
    bound = bundle["bound"]
    bound.plan["payload"]["query"] = "변경"
    bound.base["post_id"] = 999
    bound.input_rows[0]["title"] = "변경"
    assert bound.payload["query"] != "변경" and bound.base["post_id"] == 101
    with pytest.raises(FrozenInstanceError):
        bound._serialized = b"{}"
    with pytest.raises(ValueError, match="VERIFIED_FACTORY_REQUIRED"):
        contract.BoundRecoveryProviderPlan()
    assert before == {role: Path(ref["path"]).read_bytes() for role, ref in bundle["source_refs"].items()}


@pytest.mark.parametrize("field,value", [
    ("terminal_artifacts_finalized", False), ("terminal_artifacts_finalized", 1),
    ("completed_count", 1), ("flushed_count", 1), ("pending_count", 1),
    ("pending_count", False), ("partial_flush_gap", True),
    ("publication_input_snapshot_sha256", "0" * 64),
    ("publication_scope_id", "0" * 64), ("publication_scope_descriptor_sha256", "0" * 64),
    ("output_file", "relative.json"), ("run_id", ""), ("data_kind", "SOURCE_BACKED"),
])
def test_final_manifest_known_conflict_or_incomplete_is_rejected(bundle, field, value):
    kwargs = deepcopy(bundle["build_kwargs"])
    manifest = deepcopy(bundle["manifest"])
    manifest[field] = value
    replace_json(kwargs, "manifest", manifest)
    with pytest.raises(ValueError):
        contract.build_recovery_provider_plan(**kwargs)


def test_actual_manifest_without_data_kind_remains_explicit_capture_kind(bundle):
    kwargs = deepcopy(bundle["build_kwargs"])
    manifest = deepcopy(bundle["manifest"])
    manifest.pop("data_kind")
    capture = deepcopy(bundle["source_capture"])
    capture["data_kind"] = "UNKNOWN"
    replace_json(kwargs, "manifest", manifest)
    replace_json(kwargs, "source_capture", capture)
    assert contract.build_recovery_provider_plan(**kwargs)["data_kind"] == "UNKNOWN"


@pytest.mark.parametrize("role", ["result", "publication_wal"])
def test_finalized_flag_cannot_hide_missing_unselected_input_rows(bundle, role):
    kwargs = deepcopy(bundle["build_kwargs"])
    if role == "result":
        replace_json(kwargs, role, bundle["results"][:1])
    else:
        replace_raw(kwargs, role, kwargs["source_bytes"][role].splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="FULL_INPUT_REQUIRED"):
        contract.build_recovery_provider_plan(**kwargs)


@pytest.mark.parametrize("change", ["absent_capture", "old_synthetic_schema", "parent", "typed_id", "locator", "item", "raw_not_canonical", "span", "role", "query", "purpose"])
def test_original_source_proposal_and_span_cannot_be_reconstructed_or_promoted(bundle, change):
    kwargs = deepcopy(bundle["build_kwargs"])
    capture = deepcopy(bundle["source_capture"])
    if change == "absent_capture":
        del kwargs["source_refs"]["source_capture"]
        del kwargs["source_bytes"]["source_capture"]
    elif change in {"old_synthetic_schema", "parent", "typed_id", "locator", "item"}:
        if change == "old_synthetic_schema": capture["schema_version"] = "recovery_source_capture_v1"
        if change == "parent": capture["input_index"] = 2
        if change == "typed_id": capture["post_id"] = "101"
        if change == "locator": capture["source_locator"] = "image:1"
        if change == "item": capture["item"]["ocr_text"] += "다른 근거"
        replace_json(kwargs, "source_capture", capture)
    elif change == "raw_not_canonical":
        kwargs["source_binding"]["source_item_sha256"] = kwargs["source_refs"]["source_capture"]["sha256"]
    elif change == "span":
        kwargs["source_binding"]["span_start"] += 1
        kwargs["source_binding"]["span_end"] += 1
    elif change == "role": kwargs["source_binding"]["relation_role"] = "previous"
    elif change == "query": kwargs["payload"]["query"] = "근거 없는 교정 제목"
    elif change == "purpose": kwargs["payload"]["purpose"] = "UNPLANNED"
    with pytest.raises(ValueError):
        contract.build_recovery_provider_plan(**kwargs)


@pytest.mark.parametrize("change", ["result", "comment_order", "post_type", "wal_tail", "audit_hmac", "router", "plan", "scope_order"])
def test_original_publication_input_and_review_bindings_cannot_be_resealed_away(bundle, change):
    kwargs = deepcopy(bundle["build_kwargs"])
    if change == "result":
        rows = deepcopy(bundle["results"]); rows[0]["run_meta"]["extra"] = "same-decision-different-row"
        replace_json(kwargs, "result", rows)
    elif change == "comment_order":
        records = deepcopy(bundle["input_records"]); records[1]["content"] = "바뀐 댓글"
        replace_raw(kwargs, "input", b"".join(json_bytes(row) + b"\n" for row in records))
    elif change == "post_type":
        records = deepcopy(bundle["input_records"]); records[0]["post_id"] = "101"
        replace_raw(kwargs, "input", b"".join(json_bytes(row) + b"\n" for row in records))
    elif change == "wal_tail": replace_raw(kwargs, "publication_wal", kwargs["source_bytes"]["publication_wal"].rstrip(b"\n"))
    elif change == "audit_hmac": kwargs["hmac_key"] = b"wrong-audit-key-not-execution-key" * 2
    elif change in {"router", "plan"}:
        role = "router" if change == "router" else "recovery_plan"
        receipt = deepcopy(bundle[role]); receipt["post_id"] = 202
        replace_json(kwargs, role, receipt)
    else:
        scope = bundle["scope"].to_dict(); scope["post_ids"].reverse()
        replace_json(kwargs, "scope_descriptor", scope)
    with pytest.raises(ValueError):
        contract.build_recovery_provider_plan(**kwargs)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(max_calls=2), lambda p: p.update(max_calls=True),
    lambda p: p.update(request_timeout_ms=1001), lambda p: p.update(max_response_bytes=0),
    lambda p: p.update(max_total_response_bytes=-1), lambda p: p.update(retry=1),
])
def test_policy_is_explicit_single_search_with_no_hidden_retry(bundle, mutate):
    kwargs = deepcopy(bundle["build_kwargs"]); mutate(kwargs["policy"])
    with pytest.raises(ValueError): contract.build_recovery_provider_plan(**kwargs)


def test_zero_call_policy_is_valid_without_granting_dispatch(bundle):
    kwargs = deepcopy(bundle["build_kwargs"]); kwargs["policy"]["max_calls"] = 0
    assert contract.build_recovery_provider_plan(**kwargs)["policy"]["max_calls"] == 0


@pytest.mark.parametrize("endpoint", ["file:///local", "http://user:secret@127.0.0.1/mcp/search", "http://127.0.0.1/search?q=other", "http://127.0.0.1/search#other"])
def test_endpoint_is_fixed_and_contains_no_credentials_or_query(bundle, endpoint):
    kwargs = deepcopy(bundle["build_kwargs"]); kwargs["endpoint"] = endpoint
    with pytest.raises(ValueError): contract.build_recovery_provider_plan(**kwargs)


def test_path_relocation_changes_binding_not_semantic_plan_or_job(bundle, tmp_path):
    kwargs = deepcopy(bundle["build_kwargs"]); kwargs["output_dir"] = str(tmp_path / "different-output")
    moved = contract.build_recovery_provider_plan(**kwargs)
    assert moved["plan_sha256"] == bundle["plan"]["plan_sha256"]
    assert moved["job_id"] == bundle["plan"]["job_id"]
    assert moved["binding_sha256"] != bundle["plan"]["binding_sha256"]


@pytest.mark.parametrize("field", ["publication_authority", "public_apply", "central_db_write", "actual_quality_evaluated", "guard_status"])
def test_resealed_plan_cannot_claim_guard_or_public_authority(bundle, field):
    plan = deepcopy(bundle["plan"]); plan[field] = "PASS" if field == "guard_status" else True
    with pytest.raises(ValueError): contract.validate_recovery_provider_plan(contract._seal(plan))


def test_resealed_wrong_base_is_rejected_by_original_rebuild(bundle):
    plan = deepcopy(bundle["plan"]); plan["base"]["export_run_id"] = "made-up-export"
    plan = contract._seal(plan)
    assert contract.validate_recovery_provider_plan(plan) == plan
    with pytest.raises(ValueError, match="PLAN_ORIGINAL_REBUILD_MISMATCH"):
        contract.bind_recovery_provider_plan(plan, hmac_key=bundle["hmac_key"])


def test_disk_drift_and_output_source_overlap_fail_before_any_runtime(bundle):
    kwargs = deepcopy(bundle["build_kwargs"])
    kwargs["output_dir"] = str(Path(kwargs["source_refs"]["input"]["path"]).parent)
    overlap = contract.build_recovery_provider_plan(**kwargs)
    with pytest.raises(ValueError): contract.bind_recovery_provider_plan(overlap, hmac_key=bundle["hmac_key"])
    path = Path(bundle["source_refs"]["source_capture"]["path"])
    original = path.read_bytes(); path.write_bytes(original.replace(b"TEST_SYNTHETIC", b"FAKE_SYNTHETIC"))
    with pytest.raises(ValueError): bundle["bound"].verify_protected_sources()


@pytest.mark.parametrize("post_id,publication_post_id,input_format,role", [
    (101, "101", "JSON_ARRAY_V1", "previous"),
    (303, None, "JSONL_POST_COMMENT_V1", "mentioned"),
])
def test_nonprimary_role_and_typed_identifier_are_preserved(tmp_path, post_id, publication_post_id, input_format, role):
    bundle = build_recovery_provider_fixture(tmp_path, post_id=post_id, input_format=input_format,
        relation_role=role, publication_post_id=publication_post_id)
    # 숫자 문자열 허용은 공개 커밋 선택 인자에 한정하며 원문 타입은 바꾸지 않는다.
    # 원문·공개 WAL·source capture·복구 계획에는 원래 정수 ID가 그대로 남아야 한다.
    assert type(bundle["bound"].base["post_id"]) is type(post_id)
    assert bundle["bound"].base["post_id"] == post_id
    assert bundle["plan"]["source_binding"]["relation_role"] == role
    ids = [bundle["input_posts"][0]["post_id"], bundle["bound"].input_rows[0]["post_id"],
           bundle["result"]["post_id"], bundle["source_capture"]["post_id"],
           bundle["receipt"].post_id, bundle["scope"].post_ids[0],
           json.loads(bundle["source_bytes"]["publication_wal"].splitlines()[0])["receipt"]["post_id"]]
    assert all(type(value) is type(post_id) and value == post_id for value in ids)
    assert bundle["bound"].verify_protected_sources() is True
    assert all(Path(ref["path"]).read_bytes() == bundle["source_bytes"][name]
               for name, ref in bundle["source_refs"].items())


def test_non_numeric_source_identifier_is_rejected_by_existing_public_gate(tmp_path):
    # typed state의 int ID 계약을 우회하거나 None을 다른 ID로 보완하지 않는다.
    with pytest.raises(PublicationCommitError, match="post_id must be non-empty"):
        build_recovery_provider_fixture(tmp_path, post_id="text-post-id",
            input_format="JSON_ARRAY_V1", relation_role="previous")
    assert not (tmp_path / "output").exists()
    assert list((tmp_path / "source").iterdir()) == []


def test_numeric_string_raw_source_id_cannot_be_coerced_to_integer_publication(bundle):
    kwargs = deepcopy(bundle["build_kwargs"])
    records = deepcopy(bundle["input_records"])
    records[0]["post_id"] = "101"
    records[1]["post_id"] = "101"
    replace_raw(kwargs, "input", b"".join(json_bytes(row) + b"\n" for row in records))
    before = deepcopy(kwargs)
    with pytest.raises(ValueError, match="publication/input post type"):
        contract.build_recovery_provider_plan(**kwargs)
    assert kwargs == before
    assert bundle["bound"].verify_protected_sources() is True


def _projected_provider_kwargs(bundle, tmp_path, *, mode="content_blocks", mutate_source=None, mutate_result=None):
    """새 합성 경로에 입력·WAL·review·HMAC을 모두 재결속한다. 기존 bytes는 보존한다."""
    from src.llm_batch.ledger.publication_commit import (
        PUBLICATION_COMMIT_EVENT_SCHEMA, build_publication_scope_descriptor, compute_publication_decision_commit,
    )
    from src.llm_batch.ledger.recovery_activation import _create_event, extract_direct_ocr_review_proposals
    from src.llm_batch.measurement.semantic_review_router import build_semantic_review_router_receipt
    from src.llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt

    records, results = deepcopy(bundle["input_records"]), deepcopy(bundle["results"])
    post, row = records[0], results[0]
    blocks = [{"type": "paragraph", "text": "  첨부 표지를 읽었다.  "},
              {"type": "image", "image_url": " https://images.invalid/cover.png "},
              {"type": "image", "url": "https://images.invalid/cover.png"}, "  마지막 줄  "]
    post.pop("content", None)
    if mode in {"content_blocks", "both"}:
        post["content_blocks"] = deepcopy(blocks)
    if mode in {"structured_content", "both"}:
        post["content"] = deepcopy(blocks)
    if mode in {"legacy_string", "legacy_list"}:
        post["content"] = "문자열 원문" if mode == "legacy_string" else ["문자열 원문"]
        row["content"] = deepcopy(post["content"])
    else:
        row.update(content=["  첨부 표지를 읽었다.  ", "마지막 줄"], content_blocks=[
            {"type": "paragraph", "text": "첨부 표지를 읽었다."},
            {"type": "image", "url": "https://images.invalid/cover.png"},
            {"type": "image", "url": "https://images.invalid/cover.png"},
            {"type": "text", "text": "마지막 줄"}],
            image_urls=["https://images.invalid/cover.png"], image_count=1)
    if mutate_source:
        mutate_source(post)
    if mutate_result:
        mutate_result(row)
    input_raw = b"".join(json_bytes(record) + b"\n" for record in records)
    input_sha = hashlib.sha256(input_raw).hexdigest()
    scope = build_publication_scope_descriptor(input_file_sha256=input_sha,
        post_ids=[result["post_id"] for result in results], config_hash="projected-input-only",
        release_fingerprint="TEST_SYNTHETIC")
    receipts = [compute_publication_decision_commit(result, publication_scope_id=scope.publication_scope_id,
        attempt_run_id="projection-owner", input_index=index, post_id=result["post_id"])
        for index, result in enumerate(results, 1)]
    receipt = receipts[0]
    router = build_semantic_review_router_receipt(row, receipt, attempt_run_id=receipt.attempt_run_id)
    recovery = build_semantic_recovery_plan_receipt(row, receipt, attempt_run_id=receipt.attempt_run_id)
    proposal = extract_direct_ocr_review_proposals(row)[0]
    event = _create_event(receipt=receipt, proposal=proposal, raw_capability="projection-synthetic-audit",
        hmac_key=bundle["hmac_key"], sequence=1, prev_event_sha256="GENESIS")
    source_dir = tmp_path / "projected_source"
    source_dir.mkdir()
    capture = deepcopy(bundle["source_capture"])
    capture["input_raw_sha256"] = input_sha
    manifest = {**deepcopy(bundle["manifest"]), "output_file": str(source_dir / "result.json"),
        "publication_scope_id": scope.publication_scope_id, "publication_input_snapshot_sha256": input_sha,
        "publication_scope_descriptor_sha256": scope.descriptor_sha256}
    raw = {"input": input_raw, "result": json_bytes(results), "manifest": json_bytes(manifest),
        "scope_descriptor": json_bytes(scope.to_dict()), "router": json_bytes(router),
        "recovery_plan": json_bytes(recovery), "source_capture": json_bytes(capture),
        "activation_journal": json_bytes(event.to_dict()) + b"\n",
        "publication_wal": b"".join(json_bytes({"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
            "receipt": rec.to_dict(), "result": result}) + b"\n" for rec, result in zip(receipts, results))}
    refs = {}
    for role, value in raw.items():
        path = source_dir / (role + (".jsonl" if role in {"input", "publication_wal", "activation_journal"} else ".json"))
        with path.open("xb") as stream:
            stream.write(value)
        refs[role] = {"path": str(path), "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    kwargs = {**deepcopy(bundle["build_kwargs"]), "source_refs": refs, "source_bytes": raw,
        "publication_decision_id": receipt.decision_id, "activation_event_sha256": event.event_sha256,
        "output_dir": str(tmp_path / "projection_output")}
    return kwargs, post, row


@pytest.mark.parametrize("mode", ["content_blocks", "structured_content", "both", "legacy_string", "legacy_list"])
def test_provider_accepts_source_bound_main_projection_and_legacy_without_changing_bytes(bundle, tmp_path, mode):
    from src.llm_batch.measurement.recovery_input_projection import validate_main_input_projection
    before = deepcopy(bundle["source_bytes"])
    kwargs, source, row = _projected_provider_kwargs(bundle, tmp_path, mode=mode)
    arguments_before = deepcopy(kwargs)
    plan = contract.build_recovery_provider_plan(**kwargs)
    bound = contract.bind_recovery_provider_plan(plan, hmac_key=bundle["hmac_key"])
    assert bound.input_rows[0] == source
    assert bound.verify_protected_sources() is True
    assert kwargs == arguments_before
    assert all(Path(ref["path"]).read_bytes() == raw for role, raw in kwargs["source_bytes"].items()
               for ref in [kwargs["source_refs"][role]])
    assert all(Path(bundle["source_refs"][role]["path"]).read_bytes() == raw for role, raw in before.items())
    checked = validate_main_input_projection(source, row)
    if mode.startswith("legacy"):
        assert checked["mode"] == "LEGACY_TEXT_EXACT"
    else:
        # helper가 실제 loader/public helper와 일치하는지 검산한다. 전문가 실행은 없다.
        import expert_main
        post = expert_main.load_jsonl_posts(Path(kwargs["source_refs"]["input"]["path"]),
                                           snapshot_bytes=kwargs["source_bytes"]["input"])[0]
        assert post._input_truncated is False and post._parse_errors == ()
        assert checked["content"] == [block.text for block in post.content_blocks if block.text]
        assert checked["content_blocks"] == expert_main._public_content_blocks(post.content_blocks)
        assert checked["image_urls"] == expert_main._public_image_urls(post.content_blocks)
        assert checked["mode"] == "MAIN_BLOCK_PROJECTION"


def test_provider_plan_accepts_original_jsonl_post_without_comments_field(bundle, tmp_path):
    kwargs, source, row = _projected_provider_kwargs(
        bundle, tmp_path, mode="content_blocks", mutate_source=lambda post: post.pop("comments"))
    original = deepcopy(kwargs)
    plan = contract.build_recovery_provider_plan(**kwargs)
    bound = contract.bind_recovery_provider_plan(plan, hmac_key=bundle["hmac_key"])
    assert "comments" not in source and "comments" not in bound.input_rows[0]
    assert row["comments"] == bundle["result"]["comments"] == ["합성 독자 원문 댓글"]
    assert bound.verify_protected_sources() is True and kwargs == original
    assert all(Path(kwargs["source_refs"][role]["path"]).read_bytes() == raw
               for role, raw in kwargs["source_bytes"].items())


@pytest.mark.parametrize("change,code", [
    ("top_alias", "ORIGINAL_CONTENT_ALIAS_CONFLICT"),
    ("block_text_alias", "ORIGINAL_CONTENT_BLOCK_TEXT_ALIAS_CONFLICT"),
    ("block_url_alias", "ORIGINAL_CONTENT_BLOCK_URL_ALIAS_CONFLICT"),
    ("numeric_block", "ORIGINAL_CONTENT_BLOCK_UNPARSEABLE"),
    ("numeric_text", "ORIGINAL_CONTENT_BLOCK_VALUE_NOT_STRING"),
    ("unknown_field", "ORIGINAL_CONTENT_BLOCK_UNKNOWN_FIELDS"),
    ("unknown_type", "ORIGINAL_CONTENT_BLOCK_TYPE_INVALID"),
    ("missing_image_url", "ORIGINAL_IMAGE_URL_MISSING"),
    ("truncated", "ORIGINAL_INPUT_TRUNCATED_OR_INVALID"),
    ("parse_error", "ORIGINAL_INPUT_PARSE_ERRORS"),
])
def test_provider_rejects_ambiguous_source_even_after_all_hashes_and_wal_are_resealed(bundle, tmp_path, change, code):
    def mutate(post):
        blocks = post["content_blocks"]
        if change == "top_alias": post["content"] = ["다른 본문"]
        elif change == "block_text_alias": blocks[0]["content"] = "다른 본문"
        elif change == "block_url_alias": blocks[1]["url"] = "https://images.invalid/other.png"
        elif change == "numeric_block": blocks.append(42)
        elif change == "numeric_text": blocks[0]["text"] = 42
        elif change == "unknown_field": blocks[0]["html"] = "<p>숨은 원문</p>"
        elif change == "unknown_type": blocks[0]["type"] = "video"
        elif change == "missing_image_url": blocks[1].pop("image_url")
        elif change == "truncated": post["input_truncated"] = True
        elif change == "parse_error": post["parse_errors"] = ["UNJUDGED_RAW_ERROR"]
    kwargs, _, _ = _projected_provider_kwargs(bundle, tmp_path, mutate_source=mutate)
    before = deepcopy(kwargs)
    with pytest.raises(ValueError, match=code):
        contract.build_recovery_provider_plan(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize("change,code", [
    ("text", "ORIGINAL_CONTENT_PROJECTION_MISMATCH"),
    ("block_order", "ORIGINAL_CONTENT_BLOCKS_PROJECTION_MISMATCH"),
    ("block_url", "ORIGINAL_CONTENT_BLOCKS_PROJECTION_MISMATCH"),
    ("image_url", "ORIGINAL_IMAGE_URLS_PROJECTION_MISMATCH"),
    ("image_duplicates", "ORIGINAL_IMAGE_URLS_PROJECTION_MISMATCH"),
    ("image_count_bool", "ORIGINAL_IMAGE_COUNT_PROJECTION_MISMATCH"),
    ("missing_blocks", "ORIGINAL_PUBLIC_BLOCK_PROJECTION_MISSING"),
    ("missing_urls", "ORIGINAL_PUBLIC_BLOCK_PROJECTION_MISSING"),
])
def test_provider_rejects_resealed_result_projection_drift(bundle, tmp_path, change, code):
    def mutate(row):
        if change == "text": row["content"][0] += "바뀐 본문"
        elif change == "block_order": row["content_blocks"].reverse()
        elif change == "block_url": row["content_blocks"][1]["url"] = "https://images.invalid/other.png"
        elif change == "image_url": row["image_urls"][0] = "https://images.invalid/other.png"
        elif change == "image_duplicates": row["image_urls"] *= 2
        elif change == "image_count_bool": row["image_count"] = True
        elif change == "missing_blocks": row.pop("content_blocks")
        elif change == "missing_urls": row.pop("image_urls")
    kwargs, _, _ = _projected_provider_kwargs(bundle, tmp_path, mutate_result=mutate)
    with pytest.raises(ValueError, match=code):
        contract.build_recovery_provider_plan(**kwargs)


def test_public_projection_helper_is_pure_and_preserves_typed_base_values(monkeypatch):
    from src.llm_batch.measurement.recovery_input_projection import validate_main_input_projection
    source = {"gallery_id": "synthetic", "post_id": 101, "title": "합성 원문", "content": ["원문"]}
    row = {**deepcopy(source), "content_blocks": [{"type": "text", "text": "원문"}], "image_urls": []}
    before = deepcopy((source, row))
    def forbidden(*args, **kwargs):
        raise AssertionError("입력 투영 helper에서 파일 접근")
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(os, "open", forbidden)
        assert validate_main_input_projection(source, row)["content"] == ["원문"]
        row["post_id"] = "101"
        with pytest.raises(ValueError, match="ORIGINAL_INPUT_RESULT_MISMATCH"):
            validate_main_input_projection(source, row)
        row["post_id"] = 101
    assert (source, row) == before
