"""구조화 진단의 producer 결속, 공개 결과 불변, 원문 좌표와 UTF-8 크기 상한을 검증한다."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PickvelIdentity, PostInput
from llm_batch.experts.orchestrator import ConversationContext
from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics, MAX_BYTES


def native_output():
    post = PostInput(post_id=123, title="전개 감상", content_blocks=[{"type": "text", "text": "작가가 큰판을 보여줘서 좋구나"}],
                     comments=[{"author": "ㅇㅇ", "content": "친구는 그 작품이 좋다고 하더라"}])
    pipeline = AgenticPipeline(llm=object(), mcp=object(), max_iterations=2)
    ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post), comments=post.comments)
    ctx._final_source_original_inputs = pipeline._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    identity = PickvelIdentity(is_relevant=False, discussion_type="general")
    notes, verify = pipeline._consume_final_source_context(ctx, identity, None)
    assert verify()
    native = ctx._final_source_projection_native
    output = SimpleNamespace(_final_source_context_native=native, _final_source_context_owner=ctx)
    output._final_source_context_receipt = {"native_object": native, "context": ctx, "native_verification_status": "NATIVE_CALLBACK_TRUE"}
    return output, identity, notes, verify


def test_real_producer_diagnostics_preserve_public_fields_and_source_coordinates():
    output, identity, notes, verify = native_output()
    before = copy.deepcopy(identity.model_dump())
    payload = export_source_context_diagnostics(output, enabled=True)
    assert payload["status"] == "STORED"
    assert payload["publication_authority"] is False
    assert payload["projection"]["speech_act"]
    assert payload["ledgers"] and payload["channels"]
    assert any(source["raw_path"] for ledger in payload["ledgers"] for source in ledger["sources"])
    assert any(event["actor"] for ledger in payload["ledgers"] for event in ledger["evaluations"])
    assert payload["explanation"]["proofs"]
    assert any(proof["source_sha256"] and proof["raw_path"] for proof in payload["explanation"]["proofs"])
    assert identity.model_dump() == before and verify()
    assert export_source_context_diagnostics(output, enabled=False)["status"] == "OFF"
    assert identity.model_dump() == before
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "document_object" not in encoded and "native_verifier" not in encoded and "object_id" not in encoded


def test_missing_or_replaced_native_receipt_never_claims_saved_graph():
    assert export_source_context_diagnostics(object(), enabled=True)["status"] == "NOT_AVAILABLE"
    output, _, _, _ = native_output()
    output._final_source_context_native = object()
    payload = export_source_context_diagnostics(output, enabled=True)
    assert payload["status"] == "NOT_AVAILABLE" and not payload["ledgers"]


def test_diagnostics_and_process_settings_do_not_change_durable_publication_payload():
    from llm_batch.ledger.publication_commit import _stable_result_payload
    output, identity, notes, _ = native_output()
    baseline = {"post_id": 123, "analysis_result": {"identity": identity.model_dump(), "analysis": {"notes": notes}},
                "run_meta": {"model": "same-model", "run_id": "first"}}
    enriched = copy.deepcopy(baseline)
    enriched["run_meta"].update(run_id="second", execution_config={"resources": {"pid": 1234}},
                               source_context_diagnostics=export_source_context_diagnostics(output, enabled=True))
    assert _stable_result_payload(enriched) == _stable_result_payload(baseline)


def test_large_native_graph_is_utf8_bounded_with_omission_metadata_and_no_mutation():
    text = "한글진단" * 2000
    source = SimpleNamespace(source_id="author:0", text=text, raw_path="/body/0", raw_text_span=(0, len(text)))
    claim = SimpleNamespace(claim_id="c1", source_id="author:0", text=text, speaker="self")
    ledger = SimpleNamespace(source_id="author", sources=(source,) * 100, claims=(claim,) * 100,
        evaluations=(), graph_edges=(), source_role="author")
    native = SimpleNamespace(projection=SimpleNamespace(speech_act="evaluation", work_roles=((text, "reference", text),) * 100),
        author_ledger=ledger, comment_ledgers=(ledger,) * 100, channel_values=(), capture_status="CAPTURED")
    owner = SimpleNamespace()
    output = SimpleNamespace(_final_source_context_native=native, _final_source_context_owner=owner,
        _final_source_context_receipt={"native_object": native, "context": owner, "native_verification_status": "NATIVE_CALLBACK_TRUE"})
    payload = export_source_context_diagnostics(output, enabled=True)
    assert len(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) <= MAX_BYTES
    assert payload["status"] == "TRUNCATED" and payload["omitted_counts"]
    assert "BYTE_LIMIT" in payload["reason_codes"]
    assert len(native.comment_ledgers) == 100 and source.text == text


def test_expert_main_saves_diagnostics_separately_from_public_analysis():
    import ast
    tree = ast.parse((ROOT / "expert_main.py").read_text(encoding="utf-8"))
    dictionaries = [node for node in ast.walk(tree) if isinstance(node, ast.Dict)]
    def names(node):
        return {key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    run_metas = [node for node in dictionaries if {"run_id", "execution_config", "source_context_diagnostics"} <= names(node)]
    assert len(run_metas) >= 2  # 신규 분석 경로와 기존 공개 결과 참조 경로 모두 현재 실행 정보를 저장한다.
    assert any({"execution_config", "source_context_diagnostics_policy", "effective_parallel"} <= names(node) for node in dictionaries)


def test_projection_only_overflow_is_explicitly_truncated():
    values = tuple("가" * 500 for _ in range(24))
    native = SimpleNamespace(projection=SimpleNamespace(request_conditions=values, reference_works=values, excluded_works=values),
                             author_ledger=None, comment_ledgers=(), channel_values=())
    owner = SimpleNamespace()
    output = SimpleNamespace(_final_source_context_native=native, _final_source_context_owner=owner,
        _final_source_context_receipt={"native_object": native, "context": owner})
    payload = export_source_context_diagnostics(output, enabled=True)
    assert payload["status"] == "TRUNCATED"
    assert "BYTE_LIMIT" in payload["reason_codes"] and payload["omitted_counts"]["payload_sections"]
    assert len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) < MAX_BYTES
