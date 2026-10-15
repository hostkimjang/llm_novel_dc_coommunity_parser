"""일반 HTTP client의 OCR→실제 HOLD→same-call capture 경로.

외부 HTTP 응답만 합성한다. 전문가·문맥·guard·출력 모델·capture를 대체하지
않으며 기존 수동 HOLD fixture를 원래 분석 결과로 사용하지 않는다.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import threading
import zlib

import httpx

from tests.recovery_native_fixtures import TITLE, NativeHTTPFixture, native_case


BASE_ENDPOINT = "http://127.0.0.1:9"
BASE_MODEL = "synthetic-native-model"
BASE_OCR_ENV = {
    "LLM_BACKEND": "http", "LLM_SERVER_TYPE": "vllm", "LLM_MODEL": BASE_MODEL,
    "LLM_ENDPOINT": BASE_ENDPOINT, "LLM_STREAM": "0", "LLM_ENABLE_THINKING": "0",
    "LLM_VLM": "1", "LLM_OCR": "1", "LLM_MAX_RETRIES": "1",
    "LLM_MAX_TOKENS": "32768", "LLM_VLM_MAX_TOKENS": "4096",
    "LLM_DEBUG_DUMP_MESSAGES": "0", "LLM_PRINT_TIMINGS": "0",
    "MCP_ENDPOINT": BASE_ENDPOINT, "MCP_ENDPOINTS": BASE_ENDPOINT,
    "MCP_CLIENT_ENDPOINT_FAILOVER": "0", "MCP_CLIENT_SEARCH_MAX_RETRIES": "0",
    "MCP_CLIENT_SEARCH_RETRY_ON_DEGRADED_EMPTY": "0",
    "PIPELINE_ACTIVE_LEARNING_QUEUE": "0", "PIPELINE_URL_FETCH_DISK_CACHE": "0",
    "PIPELINE_SLANG_DB": "0", "PIPELINE_NATIVE_RECOVERY_MUTABLE_CONTEXT_FROZEN": "1",
    "PIPELINE_PAGE_ANALYZER_CACHE": "0", "PIPELINE_FETCH_CONCURRENCY": "1",
}


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _fixture_png():
    """제품의 MIME·geometry 검사에 실제로 통과할 16×16 합성 PNG bytes."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = b"".join(b"\0" + bytes([240, 240, 240]) * 16 for _ in range(16))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def base_ocr_case(post_id=101):
    """main 시험도 사용할 원문과 HTTP 응답. 판정 결과 객체를 반환하지 않는다."""
    if type(post_id) is not int or post_id <= 0:
        raise ValueError("fixture post_id는 양의 정수여야 한다")
    image_url = f"https://images.invalid/native/{post_id}.png"
    reason = "첨부 표지의 단일 작품을 읽은 감상이나 공식 작품 상세와 URL은 검색으로 확인되지 않았다."
    responses = deepcopy(native_case("positive")["expert_responses"])
    decoded = responses["decoder"]["decoded_terms"][0]
    decoded.update(best_match={"title": TITLE, "url": None, "confidence": "Low"},
        candidates=[{"title": TITLE, "url": None, "confidence": "Low"}],
        supporting_evidence=[], grounding={"anchor_type": "image_ocr", "anchor_text": TITLE})
    responses["decoder"]["overall_confidence"] = "low"
    relation = {"relation_type": "exact_title", "discussion_target": "specific_work",
                "promotion_decision": "hold", "confidence": "high", "reason": reason}
    verification = responses["verifier"]["verification_result"]
    verification.update(novel_identity={"official_novel_title": None, "official_title": None,
        "heretic_url": None, "confidence": "Low", "evidence_type": "image_ocr"},
        grounding_check={"anchor_found": "none", "anchor_text": None, "matched_alias": None},
        relation_judgment=deepcopy(relation), reason=reason, evidence_chain=[])
    responses["verifier"]["final_confidence"] = "low"
    responses["verifier_relation_judge"] = relation
    synthesis = responses["synthesizer"]
    synthesis["synthesis_summary"] = reason
    synthesis["reinterpretation"].update(post_intent=reason, actual_meaning=reason)
    synthesis["confidence_assessment"].update(confidence="low", requires_further_investigation=False)
    synthesis["evidence_alignment"].update(decoder_match="weak", verifier_match="weak",
        decoder_reason=reason, verifier_reason=reason)
    decision = responses["arbiter"]["final_decision"]
    decision.update(official_title=None, official_novel_title=None, heretic_url=None,
        confidence="Low", reason=reason, final_reasoning=reason)
    responses["final_semantic_reread"] = {"decision": "HOLD", "is_specific_work_discussion": True,
        "evidence_strength": "Missing", "recommended_discussion_type": "review", "reason": reason}
    responses["reason_review"].update(primary_reason=reason, merged_reason=reason)
    # 검색 근거가 없는 분석 응답에 공식 URL/페이지 사실을 끼워 넣지 않는다.
    responses["snippet_analyzer"].update(identified_title=None, identified_author=None,
        relevant_authors=[], post_intent_reason=reason)
    responses.pop("page_alive_check")
    record = {"gallery_id": "synthetic_r6", "post_id": post_id, "title": "읽고 있는 소설 후기",
        "author": "합성작성자", "created_at": "2026-10-10T09:00:00+09:00",
        "url": f"https://example.invalid/synthetic/posts/{post_id}",
        "content_blocks": [
            {"type": "text", "text": "표지에 나온 작품을 읽었다. 주인공이 적을 물리치는 전개가 좋았다."},
            {"type": "image", "url": image_url}], "comments": []}
    vlm = {"images": [{"source_url": image_url, "ocr_text": TITLE,
        "explicit_work_title": TITLE, "explicit_author_name": "합성작가",
        "visual_summary": "단일 웹소설 표지와 작품명, 작가명이 보인다.",
        "work_cues": ["웹소설", "작가명"], "confidence": "High",
        "evidence_type": "explicit_text", "surface_type": "quoted_text_screenshot", "title_role": "work_title"}],
        "chunk_summary": "첨부된 단일 작품 표지", "limitations": []}
    return {"data_kind": "TEST_SYNTHETIC", "post_record": record, "image_url": image_url,
        "image_bytes": _fixture_png(), "model": BASE_MODEL, "endpoint": BASE_ENDPOINT,
        "expert_responses": responses, "vlm_response": vlm, "environment": dict(BASE_OCR_ENV)}


class _Body(httpx.SyncByteStream):
    def __init__(self, raw): self.raw = raw
    def __iter__(self): yield self.raw


class BaseOCRHTTPFixture:
    """실제 HTTP transport 경계. 미지정 요청은 기록 후 실패하며 성공으로 숨기지 않는다."""
    def __init__(self, case_data):
        self.data = deepcopy(case_data)
        self.requests, self.tags, self.unexpected = [], [], []
        self._lock = threading.RLock()

    def install(self, monkeypatch):
        handler = self
        # httpx.get/post 및 LLM admission wrapper를 우회하지 않는다.
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda _transport, request: handler(request))

    def __call__(self, request):
        with self._lock:
            url = str(request.url)
            body = json.loads(request.content) if request.content else None
            self.requests.append({"method": request.method, "url": url, "body": deepcopy(body)})
            if request.method == "GET" and url == self.data["image_url"]:
                return httpx.Response(200, headers={"content-type": "image/png"}, stream=_Body(self.data["image_bytes"]))
            if request.method == "POST" and url == self.data["endpoint"] + "/mcp/search":
                if not isinstance(body, dict) or not body.get("query"):
                    return self._unexpected(request, body)
                result = {"query": body["query"], "results": [], "raw_total": 0, "total": 0, "degraded": False}
                if "source_receipt" in body:
                    result.update(direct_search_binding_verified=True,
                        direct_search_source_receipt_sha256=hashlib.sha256(_json_bytes(body["source_receipt"])).hexdigest())
                return self._response(result)
            if request.method != "POST" or url != self.data["endpoint"] + "/v1/chat/completions":
                return self._unexpected(request, body)
            if body.get("model") != self.data["model"] or body.get("stream") is True:
                return self._unexpected(request, body)
            system = body.get("messages", [{}])[0].get("content", "")
            if isinstance(system, str) and system.startswith("당신은 한국어 웹소설 커뮤니티 게시글의 첨부 이미지를 읽는 OCR+멀티모달 분석기다."):
                user = body["messages"][1]["content"]
                manifest = json.loads(next(item["text"] for item in user if item.get("type") == "text"))
                if ([item["source_url"] for item in manifest["images"]] != [self.data["image_url"]]
                        or not any(item.get("type") == "image_url" for item in user)):
                    return self._unexpected(request, body)
                tag, value = "vlm", self.data["vlm_response"]
            else:
                tag = NativeHTTPFixture._tag(request, body)
                if tag not in self.data["expert_responses"]:
                    return self._unexpected(request, body)
                value = self.data["expert_responses"][tag]
            self.tags.append(tag)
            return self._response({"model": self.data["model"],
                "choices": [{"message": {"role": "assistant", "content": _json_bytes(value).decode()}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 13, "total_tokens": 24}})

    def _unexpected(self, request, body):
        self.unexpected.append({"method": request.method, "url": str(request.url), "body": deepcopy(body)})
        return self._response({"error": "UNSCRIPTED_BASE_OCR_HTTP"}, status=422)

    @staticmethod
    def _response(value, status=200):
        return httpx.Response(status, headers={"content-type": "application/json"}, stream=_Body(_json_bytes(value)))


def create_base_pipeline(tmp_path, monkeypatch, *, post_id=101):
    """실행 전 fixture. process를 호출하거나 수동 ctx/HOLD를 생성하지 않는다.

    반환 keys: case/post_record/input_bytes/input_path/post/llm/mcp/pipeline/handler/http.
    main을 시험할 때는 base_ocr_case와 BaseOCRHTTPFixture만 재사용하면 된다.
    """
    from expert_main import load_jsonl_posts
    root = Path(tmp_path)
    root.mkdir(parents=True, exist_ok=True)
    case = base_ocr_case(post_id)
    for key, value in case["environment"].items(): monkeypatch.setenv(key, value)
    monkeypatch.setenv("PIPELINE_PAGE_ANALYZER_CACHE_DIR", str(root / "page_cache"))
    handler = BaseOCRHTTPFixture(case)
    handler.install(monkeypatch)
    raw = _json_bytes(case["post_record"]) + b"\n"
    path = root / "input.jsonl"
    with path.open("xb") as stream: stream.write(raw)
    loaded = load_jsonl_posts(path, snapshot_bytes=raw)
    assert len(loaded) == 1 and loaded[0].post_id == post_id
    # 실제 loader의 llm_batch 타입을 그대로 사용해 main에 capture를 넘길 수 있다.
    from llm_batch.agentic_pipeline import AgenticPipeline
    from llm_batch.llm.client import LLMClient
    from llm_batch.search.client import MCPClient
    post = loaded[0]
    assert post._input_truncated is False and post._parse_errors == ()
    llm = LLMClient(backend="http", endpoint=BASE_ENDPOINT, model=BASE_MODEL, server_type="vllm",
        stream=False, temperature=0, top_p=1, min_p=0.01, repeat_penalty=1, max_tokens=32768)
    mcp = MCPClient(endpoint=BASE_ENDPOINT, default_num_results=2)
    pipeline = AgenticPipeline(llm=llm, mcp=mcp, output_dir=root / "base_pipeline", max_iterations=2,
        parallel_count=1, batch_context_learning_enabled=False)
    pipeline._use_session_knowledge = False
    pipeline.enable_active_learning_queue = False
    return {"case": case, "post_record": deepcopy(case["post_record"]), "input_bytes": raw,
        "input_path": path, "post": post, "llm": llm, "mcp": mcp, "pipeline": pipeline,
        "handler": handler, "http": handler}


build_base_ocr_capture_fixture = create_base_pipeline


def test_actual_base_ocr_hold_review_and_same_call_capture(tmp_path, monkeypatch):
    prepared = create_base_pipeline(tmp_path, monkeypatch)
    from llm_batch.experts.orchestrator import ExpertType
    from llm_batch.ledger.publication_commit import (
        PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
        validate_publication_result_commit,
    )
    from llm_batch.ledger.recovery_activation import extract_direct_ocr_review_proposals
    from llm_batch.measurement.semantic_review_router import build_semantic_review_router_receipt
    from llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt
    import ast
    import expert_main as main
    from llm_batch.runtime.recovery_native_batch import NativeRecoveryBatchCoordinator
    from llm_batch.runtime import recovery_native_io
    from llm_batch.monitor.recovery_native_view import read_recovery_native_view
    from tests.test_recovery_native_main import commit_namespace, process_namespace, terminal_segment, execute, function
    from tests.test_recovery_native_batch import batch_policy
    from tests.recovery_native_fixtures import ENDPOINTS
    from tools import run_recovery_provider
    monkeypatch.setattr(recovery_native_io, "NATIVE_JOB_REGISTRY_ROOT", tmp_path / "native_registry")
    monkeypatch.setattr(run_recovery_provider, "_dashboard_health", lambda url: {
        "url": url, "pid": 42, "service": "expert-pipeline-monitor", "standalone": True})
    tree = next(node for node in ast.parse(Path(main.__file__).read_text(encoding="utf-8-sig")).body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    ns = commit_namespace(tmp_path, tree, post_ids=[prepared["post"].post_id], input_bytes=prepared["input_bytes"])
    native_handler = NativeHTTPFixture(native_case("positive"))
    policy = batch_policy()
    policy["native_config"].update(server_type="vllm", min_p=0.01, repeat_penalty=1,
                                   vllm_top_k=20, vllm_presence_penalty=1.5)
    coordinator = NativeRecoveryBatchCoordinator(policy=policy, input_post_ids=[prepared["post"].post_id],
        input_snapshot_bytes=prepared["input_bytes"], input_path=prepared["input_path"],
        output_dir=tmp_path / "native_batch", root=tmp_path, hmac_key_path=tmp_path / "activation.hex",
        dashboard_url="http://127.0.0.1:8080", data_kind="TEST_SYNTHETIC",
        test_transport=httpx.MockTransport(native_handler), clock_ms=lambda: 2000,
        run_id=ns["ts"], publication_scope_id=ns["publication_scope_id"])
    ns["_native_recovery_batch"] = coordinator
    process_namespace(ns, tree, tmp_path)
    post, pipeline, http = prepared["post"], prepared["pipeline"], prepared["http"]
    source_before = post.model_dump(mode="json")
    wrapped = ns["_process_one"](post, 1, 1, pipeline, 0)
    output, capture = wrapped._source_output, wrapped._native_capture
    assert not http.unexpected, http.unexpected
    assert capture is not None and capture.verify_current() is True
    assert type(pipeline.llm).__name__ == "LLMClient" and type(pipeline.mcp).__name__ == "MCPClient"
    assert type(pipeline).__module__ == "llm_batch.agentic_pipeline"
    assert type(capture).__module__ == "llm_batch.runtime.recovery_native_context"
    assert pipeline._native_recovery is False
    assert http.tags.count("vlm") == 1
    assert {"gatekeeper", "decoder", "verifier", "arbiter"} <= set(http.tags)
    assert sum(request["url"] == prepared["case"]["image_url"] for request in http.requests) == 1
    assert any(request["url"].endswith("/mcp/search") for request in http.requests)
    owner = output.__dict__["_final_source_context_owner"]
    cloned = capture.clone_context()
    assert cloned is not owner and cloned.post_id == owner.post_id == post.post_id
    assert cloned.get_expert_output(ExpertType.GATEKEEPER)
    assert cloned.get_expert_output(ExpertType.DECODER)
    assert cloned.post_data["vlm_enrichment_used"] is True
    assert cloned.post_data["image_fetch_success"] == cloned.post_data["vlm_chunks_sent"] == 1
    assert capture.source_snapshot == {"payload": source_before, "input_truncated": False, "parse_errors": []}
    assert post.model_dump(mode="json") == source_before and prepared["input_path"].read_bytes() == prepared["input_bytes"]

    payload = output.model_dump(mode="json")
    pipeline.verify_final_source_context_serialization(output, payload, stage="base_ocr_test")
    identity = payload["identity"]
    assert identity["promotion_decision"]["publish_allowed"] is False, identity
    assert not (identity.get("novel_identity") or {}).get("official_title")
    assert not (identity.get("novel_identity") or {}).get("heretic_url")
    catalog = identity["image_evidence_catalog"]
    assert len(catalog) == 1 and catalog[0]["explicit_work_title"] == TITLE
    assert catalog[0]["ocr_text"] == TITLE and catalog[0]["promotion_eligible"] is True
    assert catalog[0]["title_role"] == "work_title" and catalog[0]["evidence_type"] == "explicit_text"
    assert catalog[0]["source_url"] == prepared["case"]["image_url"]
    # 실제 main의 commit/AUDIT/인계 closure를 그대로 실행한다.
    receipt, created, canonical = ns["commit"](wrapped, global_idx=1, post_id=post.post_id)
    registry = ns["publication_commit_registry"]
    assert created and receipt.outcome == "HOLD"
    validate_publication_result_commit(wrapped, receipt, expected_scope_id=ns["publication_scope_id"],
                                      expected_input_index=1, expected_post_id=post.post_id)
    router = canonical["run_meta"]["semantic_review_router_receipt"]
    recovery = canonical["run_meta"]["semantic_recovery_plan_receipt"]
    proposals = extract_direct_ocr_review_proposals(wrapped)
    assert router["state"] == "REVIEW_REQUIRED", router
    assert recovery["plan"]["state"] == "HOLD", recovery
    assert len(proposals) == 1 and proposals[0].raw_candidate_title == TITLE
    assert proposals[0].source_kind == "direct_image_ocr" and proposals[0].source_locator == catalog[0]["eid"]
    assert proposals[0].source_payload_sha256 == hashlib.sha256(_json_bytes(catalog[0])).hexdigest()
    assert capture.verify_current() is True and output.model_dump(mode="json") == payload
    assert wrapped.take_native_capture() is None
    assert coordinator.summary()["rows"][0]["capture_status"] == "CAPTURED"
    assert not native_handler.requests
    output_path, manifest_path = tmp_path / "result.json", tmp_path / "manifest.json"
    execute([function(tree, "_fsync_parent_directory"), function(tree, "_atomic_write_text"),
             function(tree, "_atomic_write_json")], ns)
    ns["_atomic_write_json"](output_path, [canonical])
    protected_paths = [prepared["input_path"], output_path, registry.path, registry.scope_descriptor_path,
                       tmp_path / "activation.jsonl"]
    protected = {path: path.read_bytes() for path in protected_paths}
    fields = {"input_post_count": 1, "data_kind": "TEST_SYNTHETIC", "publication_scope_id": ns["publication_scope_id"],
        "publication_scope_descriptor_sha256": registry.scope_descriptor.descriptor_sha256,
        "publication_input_snapshot_sha256": hashlib.sha256(prepared["input_bytes"]).hexdigest(),
        **main._native_recovery_manifest_fields({"policy": policy, "policy_file_sha256": "a" * 64}, output_path)}
    ns.update(_terminal_artifacts_finalized=False, result_manifest_path=manifest_path, out_result_path=output_path,
        checkpoint_jsonl_path=tmp_path / "checkpoint.jsonl", pending_snapshot_path=tmp_path / "pending.json",
        results=[canonical], _sequential_failed_count=0, _parallel_manifest_fields=lambda: deepcopy(fields),
        _completion_manifest_gate_fields=lambda **kwargs: {"terminal_artifacts_finalized": ns["_terminal_artifacts_finalized"]},
        publication_commit_journal_path=registry.path, recovery_activation_journal_path=tmp_path / "activation.jsonl")
    execute(terminal_segment(tree), ns)
    report = ns["_native_recovery_report"]
    assert report["status"] == "COMPLETED", report
    assert report["rows"][0]["execution_status"] == "COMPLETED_NATIVE_IO", report
    assert report["rows"][0]["guard_outcome"] == "PUBLISH", report
    assert report["counts"]["actual_external_calls"] == 0
    assert all(path.read_bytes() == raw for path, raw in protected.items())
    view = read_recovery_native_view(output_path, tmp_path, item=canonical)
    assert view["binding_status"] == "BOUND", view
    assert view["row"]["native"]["guard_status"] == "PUBLISH"
    assert view["row"]["provider"]["guard_status"] == "GUARD_NOT_EVALUATED"
    assert view["row"]["native"]["publication_scope_id"] != ns["publication_scope_id"]
